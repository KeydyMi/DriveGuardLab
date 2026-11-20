"""Ejecuta los escenarios sintéticos de conducción y guarda un resumen reproducible.

Uso:
    python scripts/experimentos/escenarios_sinteticos.py
    python scripts/experimentos/escenarios_sinteticos.py --semilla 7 --fps 15 --salida resultados
    python scripts/experimentos/escenarios_sinteticos.py --escenarios normal,microsueno

Salida (solo CSV/MD):
    resultados/escenarios_sinteticos.csv  mediciones y estados por fotograma
    resultados/escenarios_sinteticos.md   resumen de hallazgos por escenario

No modifica los valores por defecto de ConfigRiesgo: usa `ConfigRiesgo()` tal cual.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402

from core.config import ROOT, ConfigRiesgo  # noqa: E402
from core.riesgo import ORDEN  # noqa: E402
from core.simulacion import ESCENARIOS, ejecutar, generar_mediciones  # noqa: E402

ESPERADO = {
    "normal": ("Conducción estable, sin alertas", "NORMAL", False),
    "cansancio": ("MEDIO por PERCLOS alto y bostezos", "MEDIO", False),
    "microsueno": ("ALTO por cierre continuo de ojos", "ALTO", False),
    "sin_respuesta": ("ALTO y emergencia tras no responder", "ALTO", True),
    "distraccion": ("MEDIO por giro de cabeza", "MEDIO", False),
    "cabeceos": ("MEDIO por cabeceos repetidos", "MEDIO", False),
    "rostro_ausente": ("MEDIO por rostro no visible", "MEDIO", False),
}


def _primer_t(datos: pd.DataFrame, nivel: str) -> float | None:
    filas = datos[datos.nivel == nivel]
    return float(filas.t.iloc[0]) if not filas.empty else None


def _fmt_t(valor: float | None) -> str:
    # Al construir el DataFrame, los None pasan a ser NaN; ambos significan "no ocurrió".
    return "—" if valor is None or pd.isna(valor) else f"{valor:.1f} s"


def _round_t(valor: float | None) -> float | None:
    return None if valor is None else round(valor, 2)


def resumir(escenario: str, df: pd.DataFrame, fps: int) -> tuple[dict, str]:
    """Devuelve una fila de métricas y el hallazgo en lenguaje natural."""
    datos = df[~df.calibrando]
    motivos = sorted({m for fila in datos.motivos for m in fila.split(",") if m})
    nivel_max = max(datos.nivel, key=lambda n: ORDEN[n])
    emergentes = datos[datos.emergencia]
    primera_emergencia = float(emergentes.t.iloc[0]) if not emergentes.empty else None

    fila = {
        "escenario": escenario,
        "esperado": ESPERADO.get(escenario, ("—", "—", False))[0],
        "duracion_s": round(float(datos.t.iloc[-1] + 1 / fps), 2),
        "frames": int(len(datos)),
        "calibracion_s": round(float(datos.t.iloc[0]), 2),
        "ear_base": round(float(datos.ear_base.dropna().iloc[-1]), 4),
        "ear_umbral": round(float(datos.ear_umbral.iloc[-1]), 4),
        "nivel_max": nivel_max,
        "primer_bajo_s": _round_t(_primer_t(datos, "BAJO")),
        "primer_medio_s": _round_t(_primer_t(datos, "MEDIO")),
        "primer_alto_s": _round_t(_primer_t(datos, "ALTO")),
        "s_normal": round(int((datos.nivel == "NORMAL").sum()) / fps, 2),
        "s_bajo": round(int((datos.nivel == "BAJO").sum()) / fps, 2),
        "s_medio": round(int((datos.nivel == "MEDIO").sum()) / fps, 2),
        "s_alto": round(int((datos.nivel == "ALTO").sum()) / fps, 2),
        "perclos_max": round(float(datos.perclos.max()), 4),
        "bostezos_max": int(datos.bostezos.max()),
        "cabeceos_max": int(datos.cabeceos.max()),
        "cierre_max_s": round(float(datos.tiempo_ojos_cerrados.max()), 2),
        "motivos": ";".join(motivos),
        "primera_emergencia_s": round(primera_emergencia, 2) if primera_emergencia is not None else None,
        "frames_emergencia": int(datos.emergencia.sum()),
    }

    partes = []
    if nivel_max == "NORMAL":
        partes.append(f"sin alertas en {fila['duracion_s']:.0f} s; cierre máximo {fila['cierre_max_s']:.2f} s "
                      "(parpadeos normales)")
    if "microsueno" in motivos:
        partes.append(f"ALTO a los {_fmt_t(fila['primer_alto_s'])} por {fila['cierre_max_s']:.1f} s "
                      "de ojos cerrados de forma continua")
    if "cansancio_perclos" in motivos:
        partes.append(f"PERCLOS máximo {fila['perclos_max']:.0%} (umbral 30 %)")
    if "bostezos" in motivos:
        partes.append(f"{fila['bostezos_max']} bostezos en la ventana de 5 min")
    if "cabeceos" in motivos:
        partes.append(f"{fila['cabeceos_max']} cabeceos -> MEDIO")
    if "distraccion" in motivos:
        partes.append(f"giro de cabeza -> MEDIO a los {_fmt_t(fila['primer_medio_s'])}")
    if "rostro_ausente" in motivos:
        partes.append(f"rostro no visible -> MEDIO a los {_fmt_t(fila['primer_medio_s'])}")
    if "cabeza_caida" in motivos:
        partes.append("cabeza caída prolongada -> ALTO")
    if fila["primera_emergencia_s"] is not None:
        partes.append(f"emergencia a los {_fmt_t(fila['primera_emergencia_s'])} "
                      "(ALTO sin respuesta durante 10 s)")
    texto = "; ".join(partes)
    hallazgo = texto[0].upper() + texto[1:] + "."
    return fila, hallazgo


def escribir_md(ruta: Path, resumen: pd.DataFrame, hallazgos: dict[str, str],
                semilla: int, fps: int, nombres: list[str]) -> None:
    config = ConfigRiesgo()
    lineas = [
        "# Escenarios sintéticos de conducción",
        "",
        "Reproducir: `python scripts/experimentos/escenarios_sinteticos.py "
        f"--semilla {semilla} --fps {fps} --salida {ruta.parent.name}`",
        "",
        f"- Escenarios ejecutados: {', '.join(nombres)}.",
        f"- Semilla: `{semilla}`; muestreo: `{fps}` fps; `core.simulacion.generar_mediciones` "
        "+ `core.simulacion.ejecutar`.",
        f"- Umbrales: `ConfigRiesgo()` sin cambios (calibración {config.calibracion_s:g} s, "
        f"factor EAR {config.factor_ear:g}, PERCLOS {config.perclos_umbral:.0%}, "
        f"microsueño {config.microsueno_s:g} s, histeresis {config.histeresis_s:g} s, "
        f"sin respuesta {config.sin_respuesta_s:g} s).",
        "- Datos por fotograma: `escenarios_sinteticos.csv`. No se guardan imágenes ni se usa cámara.",
        "",
        "## Resultados",
        "",
        "| Escenario | Nivel máx. | Primer MEDIO | Primer ALTO | Motivos | PERCLOS máx. | "
        "Bostezos | Cabeceos | Cierre máx. | Emergencia |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, r in resumen.iterrows():
        motivos = r.motivos.replace(";", ", ") or "—"
        emergencia = _fmt_t(r.primera_emergencia_s) if pd.notna(r.primera_emergencia_s) else "No"
        lineas.append(
            f"| {r.escenario} | {r.nivel_max} | {_fmt_t(r.primer_medio_s)} | "
            f"{_fmt_t(r.primer_alto_s)} | {motivos} | {r.perclos_max:.0%} | "
            f"{r.bostezos_max} | {r.cabeceos_max} | {r.cierre_max_s:.1f} s | {emergencia} |"
        )
    lineas += ["", "## Hallazgos por escenario", ""]
    for nombre in nombres:
        r = resumen[resumen.escenario == nombre].iloc[0]
        _, nivel_esperado, emergencia_esperada = ESPERADO.get(
            nombre, ("—", "—", False))
        conforme = (r.nivel_max == nivel_esperado and
                    bool(pd.notna(r.primera_emergencia_s)) == emergencia_esperada)
        lineas.append(f"- **{nombre}** (esperado: {r.esperado}) — {hallazgos[nombre]} "
                      f"[{'OK' if conforme else 'REVISAR'}]")
    lineas += [
        "",
        "Nota: el primer MEDIO/ALTO se mide después de la calibración inicial. "
        "La emergencia de `sin_respuesta` se cancelaría con «Estoy bien» "
        "(`MotorRiesgo.reconocer`), no ejercitado en esta corrida.",
        "",
    ]
    ruta.write_text("\n".join(lineas), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=int, default=42, help="semilla del ruido sintético (def. 42)")
    parser.add_argument("--fps", type=int, default=15, help="fotogramas por segundo (def. 15)")
    parser.add_argument("--salida", type=Path, default=ROOT / "resultados",
                        help="directorio de salida (def. resultados/)")
    parser.add_argument("--escenarios", default=",".join(ESCENARIOS),
                        help="lista separada por comas (def. todos)")
    args = parser.parse_args()

    if args.fps <= 0:
        parser.error("--fps debe ser positivo")
    nombres = [n.strip() for n in args.escenarios.split(",") if n.strip()]
    desconocidos = [n for n in nombres if n not in ESCENARIOS]
    if desconocidos:
        parser.error(f"escenarios desconocidos: {desconocidos}. Opciones: {list(ESCENARIOS)}")

    args.salida.mkdir(parents=True, exist_ok=True)
    csv_path = args.salida / "escenarios_sinteticos.csv"
    md_path = args.salida / "escenarios_sinteticos.md"

    tablas, filas, hallazgos = [], [], {}
    for nombre in nombres:
        mediciones = generar_mediciones(nombre, fps=args.fps, semilla=args.semilla)
        df = ejecutar(mediciones)
        df.insert(0, "escenario", nombre)
        tablas.append(df)
        fila, hallazgo = resumir(nombre, df, args.fps)
        filas.append(fila)
        hallazgos[nombre] = hallazgo
        print(f"[OK] {nombre:14s} {len(df):4d} fotogramas -> {fila['nivel_max']}: {hallazgo}")

    pd.concat(tablas, ignore_index=True).to_csv(csv_path, index=False, encoding="utf-8-sig")
    resumen = pd.DataFrame(filas)
    escribir_md(md_path, resumen, hallazgos, args.semilla, args.fps, nombres)
    print(f"[OK] CSV: {csv_path}")
    print(f"[OK] MD:  {md_path}")


if __name__ == "__main__":
    main()
