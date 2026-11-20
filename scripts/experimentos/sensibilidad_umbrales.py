"""Análisis de sensibilidad de umbrales (EAR, PERCLOS y tiempos de respuesta).

Barre los umbrales de `ConfigRiesgo` sobre los escenarios sintéticos de
`core.simulacion`, sin tocar los valores por defecto ni `.env`. Cada valor se
evalúa con las MISMAS mediciones (semilla fija), de modo que las diferencias
entre filas se deben solo al umbral barrido.

Uso:
    python scripts/experimentos/sensibilidad_umbrales.py
    python scripts/experimentos/sensibilidad_umbrales.py --semilla 7 --fps 15
    python scripts/experimentos/sensibilidad_umbrales.py --parametros factor_ear,perclos_umbral

Salida (solo CSV/PNG/MD, en resultados/):
    sensibilidad_umbrales.csv            una fila por valor barrido con métricas y recomendación
    sensibilidad_umbrales_detalles.csv   una fila por caso evaluado (trazabilidad de detecciones)
    sensibilidad_umbrales.png            5 paneles: detecciones vs. falsas alarmas por umbral
    sensibilidad_umbrales.md             tablas, impacto por ajuste y recomendaciones
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core.config import ROOT, ConfigRiesgo  # noqa: E402
from core.riesgo import ORDEN  # noqa: E402
from core.simulacion import ESCENARIOS, ejecutar, generar_mediciones  # noqa: E402


@dataclass(frozen=True)
class Caso:
    """Un escenario positivo con verdad conocida (inicio/fin del evento)."""

    escenario: str
    nivel: str                       # nivel mínimo esperado
    motivo: str | None               # motivo esperado; None = solo nivel
    inicio_s: float                  # inicio del evento
    fin_s: float | None = None       # fin del evento (para alertas tardías / bajada)
    emergencia: bool = False         # exige además emergencia=True


@dataclass(frozen=True)
class Barrido:
    """Un parámetro de ConfigRiesgo a barrer y los casos con los que se juzga."""

    parametro: str
    grupo: str
    valores: tuple[float, ...]
    casos: tuple[Caso, ...]
    latencia_tipo: str               # "deteccion" | "bajada"
    etiqueta: str


BARRIDOS: tuple[Barrido, ...] = (
    Barrido(
        "factor_ear", "EAR", (0.20, 0.25, 0.30, 0.35, 0.50, 0.75, 0.95),
        (Caso("microsueno", "ALTO", "microsueno", 20.0, 22.5),
         Caso("sin_respuesta", "ALTO", "microsueno", 20.0, 42.0)),
        "deteccion", "Factor del EAR base",
    ),
    Barrido(
        "perclos_umbral", "PERCLOS", (0.02, 0.05, 0.10, 0.20, 0.30, 0.35, 0.40, 0.50),
        (Caso("cansancio", "MEDIO", "cansancio_perclos", 15.0),),
        "deteccion", "Umbral de PERCLOS",
    ),
    Barrido(
        "microsueno_s", "TIEMPOS", (0.5, 1.0, 1.5, 2.0, 2.5, 3.0),
        (Caso("microsueno", "ALTO", "microsueno", 20.0, 22.5),
         Caso("sin_respuesta", "ALTO", "microsueno", 20.0, 42.0)),
        "deteccion", "Microsueño: cierre continuo (s)",
    ),
    Barrido(
        "sin_respuesta_s", "TIEMPOS", (3.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0),
        (Caso("sin_respuesta", "ALTO", "microsueno", 20.0, None, True),),
        "deteccion", "Sin respuesta → emergencia (s)",
    ),
    Barrido(
        "histeresis_s", "TIEMPOS", (0.0, 0.5, 1.0, 2.0, 4.0, 6.0, 10.0),
        (Caso("microsueno", "ALTO", None, 20.0, 22.5),
         Caso("distraccion", "MEDIO", None, 20.0, 25.0)),
        "bajada", "Histéresis al bajar de nivel (s)",
    ),
)


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------
def _post(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta los fotogramas de calibración."""
    return df[~df.calibrando]


def _segundos_alerta(df: pd.DataFrame, fps: int) -> float:
    """Segundos con nivel != NORMAL en el DataFrame recibido."""
    if df.empty:
        return 0.0
    return round(float((df.nivel != "NORMAL").sum()) / fps, 2)


def _primera_deteccion(df: pd.DataFrame, caso: Caso) -> float | None:
    """Primer instante (tras el inicio del evento) que satisface el caso."""
    sel = df[(df.t >= caso.inicio_s) & (df.nivel.map(ORDEN) >= ORDEN[caso.nivel])]
    if caso.motivo is not None:
        sel = sel[sel.motivos.str.contains(caso.motivo, regex=False)]
    if caso.emergencia:
        sel = sel[sel.emergencia]
    return float(sel.t.iloc[0]) if not sel.empty else None


def _retorno_normal(df: pd.DataFrame, fin_s: float) -> float | None:
    """Segundos entre el fin del evento y el primer fotograma NORMAL."""
    normales = df[(df.t >= fin_s) & (df.nivel == "NORMAL")]
    return float(normales.t.iloc[0]) - fin_s if not normales.empty else None


def evaluar_valor(barrido: Barrido, valor: float, mediciones: dict,
                  fps: int) -> tuple[dict, list[dict]]:
    """Evalúa un valor del barrido y devuelve (fila agregada, filas de detalle)."""
    cfg = ConfigRiesgo.desde_dict({barrido.parametro: valor})
    detalles: list[dict] = []
    latencias: list[float] = []
    detectados: list[str] = []
    fallidos: list[str] = []
    anticipadas = tardias = 0.0

    for caso in barrido.casos:
        post = _post(ejecutar(mediciones[caso.escenario], config=cfg))
        t_det = _primera_deteccion(post, caso)
        latencia = retorno = None
        if t_det is not None:
            detectados.append(caso.escenario)
            if barrido.latencia_tipo == "deteccion":
                latencia = round(t_det - caso.inicio_s, 2)
                latencias.append(latencia)
        else:
            fallidos.append(caso.escenario)

        # Alertas fuera de la ventana del evento = falsas alarmas.
        anticipadas += _segundos_alerta(post[post.t < caso.inicio_s], fps)
        if caso.fin_s is not None:
            tardias += _segundos_alerta(post[post.t >= caso.fin_s], fps)
            if barrido.latencia_tipo == "bajada" and t_det is not None:
                retorno = _retorno_normal(post, caso.fin_s)
                if retorno is not None:
                    latencias.append(retorno)

        detalles.append({
            "parametro": barrido.parametro,
            "valor": valor,
            "escenario": caso.escenario,
            "nivel_esperado": caso.nivel,
            "detectado": t_det is not None,
            "primera_deteccion_s": None if t_det is None else round(t_det, 2),
            "latencia_s": latencia,
            "retorno_normal_s": None if retorno is None else round(retorno, 2),
            "s_alerta_anticipada": _segundos_alerta(post[post.t < caso.inicio_s], fps),
            "s_alerta_tardia": (_segundos_alerta(post[post.t >= caso.fin_s], fps)
                                if caso.fin_s is not None else 0.0),
        })

    falsas = _segundos_alerta(_post(ejecutar(mediciones["normal"], config=cfg)), fps)
    fila = {
        "parametro": barrido.parametro,
        "grupo": barrido.grupo,
        "valor": valor,
        "por_defecto": bool(np.isclose(valor, getattr(ConfigRiesgo(), barrido.parametro))),
        "detecciones": f"{len(detectados)}/{len(barrido.casos)}",
        "casos_fallidos": ";".join(fallidos),
        "falsas_alarmas_s": falsas,
        "alertas_anticipadas_s": round(anticipadas, 2),
        "alertas_tardias_s": round(tardias, 2),
        "latencia_s": round(float(np.mean(latencias)), 2) if latencias else None,
        "latencia_tipo": barrido.latencia_tipo,
    }
    return fila, detalles


def recomendar(barrido: Barrido, tabla: pd.DataFrame) -> tuple[float | None, str]:
    """Elige el valor factible: todas las detecciones, cero falsas alarmas.

    Si el default es factible se conserva. En caso contrario se propone el
    valor factible más cercano al default (criterio conservador).
    """
    defecto = getattr(ConfigRiesgo(), barrido.parametro)
    n = len(barrido.casos)
    factibles = tabla[(tabla.detecciones == f"{n}/{n}") &
                      (tabla.falsas_alarmas_s == 0) &
                      (tabla.alertas_anticipadas_s == 0) &
                      tabla.latencia_s.notna()]
    if factibles.empty:
        return None, "Sin valor factible: revisar los escenarios o el resto de umbrales."
    if np.any(np.isclose(factibles.valor, defecto)):
        return defecto, "El valor por defecto ya detecta todos los casos sin falsas alarmas; se conserva."
    mejor = min(factibles.valor, key=lambda v: abs(v - defecto))
    return float(mejor), "El default falla en algún caso; se propone el valor factible más cercano."


# --------------------------------------------------------------------------
# Presentación
# --------------------------------------------------------------------------
def _valor_texto(barrido: Barrido, valor: float) -> str:
    if barrido.parametro == "perclos_umbral":
        return f"{valor * 100:g} %"
    if barrido.parametro.endswith("_s"):
        return f"{valor:g} s"
    return f"{valor:g}"


def _tiempo(valor: float | None) -> str:
    return "—" if valor is None or pd.isna(valor) else f"{valor:.2f} s"


def escribir_md(ruta: Path, salida: pd.DataFrame, recomendaciones: dict,
                notas: dict, semilla: int, fps: int, nombres: list[str]) -> None:
    cfg = ConfigRiesgo()
    lineas = [
        "# Sensibilidad de umbrales: EAR, PERCLOS y tiempos de respuesta",
        "",
        "Reproducir: `python scripts/experimentos/sensibilidad_umbrales.py "
        f"--semilla {semilla} --fps {fps} --salida {ruta.parent.name}`",
        "",
        f"- Semilla `{semilla}`; `{fps}` fps; escenarios: {', '.join(nombres)}.",
        "- Los umbrales se aplican con `ConfigRiesgo.desde_dict(...)`; "
        "**los valores por defecto de `ConfigRiesgo` no se modifican** y no se lee/escribe `.env`.",
        "- Cada valor se evalúa sobre las mismas mediciones (ruido con semilla fija): "
        "las diferencias entre filas se deben solo al umbral barrido.",
        "- **Detecciones**: casos con el nivel/motivo (y emergencia cuando aplica) esperados "
        "después del inicio del evento. **Falsas alarmas**: segundos con nivel != NORMAL en "
        "`normal` más las alertas fuera de la ventana del evento "
        "(anticipadas/tardías, columnas separadas).",
        f"- Referencia: calibración {cfg.calibracion_s:g} s, factor EAR {cfg.factor_ear:g}, "
        f"PERCLOS {cfg.perclos_umbral:.0%}, microsueño {cfg.microsueno_s:g} s, "
        f"sin respuesta {cfg.sin_respuesta_s:g} s, histéresis {cfg.histeresis_s:g} s.",
        "",
    ]
    for barrido in BARRIDOS:
        tabla = salida[salida.parametro == barrido.parametro]
        if tabla.empty:
            continue
        recomendado, nota = recomendaciones[barrido.parametro]
        etiqueta = "detección" if barrido.latencia_tipo == "deteccion" else "retorno a NORMAL"
        lineas += [
            f"## {barrido.grupo}: `{barrido.parametro}`",
            "",
            f"Parámetro de la pestaña *Configuración*: **{barrido.etiqueta}**. "
            f"Casos evaluados: {', '.join(c.escenario for c in barrido.casos)}.",
            "",
            "| Valor | Detecciones | Falsas alarmas (normal) | Alertas anticipadas | "
            f"Alertas tardías | {etiqueta.capitalize()} | Default | Recomendado |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for _, r in tabla.iterrows():
            lineas.append(
                f"| {_valor_texto(barrido, r.valor)} | {r.detecciones} | "
                f"{r.falsas_alarmas_s:.2f} s | {r.alertas_anticipadas_s:.2f} s | "
                f"{r.alertas_tardias_s:.2f} s | {_tiempo(r.latencia_s)} | "
                f"{'sí' if r.por_defecto else 'no'} | "
                f"{'sí' if np.isclose(r.valor, recomendado) else 'no'} |"
            )
        lineas += ["", f"**Recomendado: {_valor_texto(barrido, recomendado)}** — {nota}",
                   "", f"Impacto: {notas[barrido.parametro]}", ""]

    lineas += [
        "## Conclusión",
        "",
        "Los ajustes más sensibles son los que cruzan la ventana del evento: un EAR demasiado "
        "bajo deja de reconocer ojos cerrados, un PERCLOS demasiado alto pierde el cansancio y "
        "un `microsueno_s` mayor que el cierre sintético (2,5 s) elimina la alerta ALTO. "
        "`sin_respuesta_s` solo desplaza el momento de la emergencia, y `histeresis_s` "
        "no retrasa la subida de nivel pero sí el retorno a NORMAL.",
        "",
        "La recomendación se calcula sobre estos escenarios sintéticos; no sustituye una "
        "validación con conductores reales y **no cambia los defaults** de la aplicación.",
        "",
    ]
    ruta.write_text("\n".join(lineas), encoding="utf-8")


def _impacto(barrido: Barrido, tabla: pd.DataFrame, recomendado: float | None) -> str:
    n = len(barrido.casos)
    partes = []
    fallidos = tabla[tabla.detecciones != f"{n}/{n}"]
    if not fallidos.empty:
        valores = ", ".join(_valor_texto(barrido, v) for v in fallidos.valor)
        partes.append(f"pierden detecciones con {valores}")
    con_falsas = tabla[tabla.falsas_alarmas_s > 0]
    if not con_falsas.empty:
        valores = ", ".join(f"{_valor_texto(barrido, v)} ({r.falsas_alarmas_s:g} s)"
                            for v, r in zip(con_falsas.valor, con_falsas.itertuples()))
        partes.append(f"falsas alarmas en `normal` con {valores}")
    tardias = tabla.alertas_tardias_s
    if tardias.max() - tardias.min() > 0.5:
        partes.append(f"las alertas tardías van de {tardias.min():g} s a {tardias.max():g} s")
    fila_def = tabla[tabla.por_defecto]
    if not fila_def.empty:
        r = fila_def.iloc[0]
        partes.append(f"el default da {r.detecciones} con {r.falsas_alarmas_s:g} s de falsas "
                      f"alarmas y {_tiempo(r.latencia_s)} de "
                      f"{'detección' if barrido.latencia_tipo == 'deteccion' else 'retorno'}")
    if recomendado is not None:
        fila_rec = tabla[np.isclose(tabla.valor, recomendado)]
        if not fila_rec.empty:
            r = fila_rec.iloc[0]
            partes.append(f"la recomendación ({_valor_texto(barrido, recomendado)}) "
                          f"da {r.detecciones} y {_tiempo(r.latencia_s)}")
    texto = "; ".join(partes)
    return texto[0].upper() + texto[1:] + "."


def graficar(ruta: Path, salida: pd.DataFrame, recomendaciones: dict) -> None:
    fig, ejes = plt.subplots(2, 3, figsize=(15, 8))
    planos = [e for fila in ejes for e in fila]
    for eje, barrido in zip(planos, BARRIDOS):
        tabla = salida[salida.parametro == barrido.parametro].sort_values("valor")
        if tabla.empty:
            eje.set_visible(False)
            continue
        n = len(barrido.casos)
        detections = [int(v.split("/")[0]) / n * 100 for v in tabla.detecciones]
        lineas1 = eje.plot(tabla.valor, detections, "o-", color="#1f77b4",
                           label="Detecciones (%)")
        etiquetas1 = ["Detecciones (%)"]
        eje.axvline(getattr(ConfigRiesgo(), barrido.parametro), color="0.5", ls=":",
                    lw=1.5, label="Default")
        reco = recomendaciones[barrido.parametro][0]
        if reco is not None:
            eje.axvline(reco, color="#2ca02c", ls="--", lw=1.5, label="Recomendado")
        eje.set_title(barrido.etiqueta, fontsize=10)
        eje.set_xlabel(_eje_x(barrido))
        eje.set_ylabel("Detecciones (%)", color="#1f77b4")
        eje.set_ylim(-5, 105)
        eje.grid(alpha=0.25)

        eje2 = eje.twinx()
        lineas2 = eje2.plot(tabla.valor, tabla.falsas_alarmas_s, "s--", color="#d62728",
                            label="Falsas alarmas (s)")
        etiquetas2 = ["Falsas alarmas (s)"]
        eje2.set_ylabel("Falsas alarmas (s)", color="#d62728")
        eje.legend(lineas1 + lineas2 + [eje.lines[1]],
                   etiquetas1 + etiquetas2 + ["Default"], loc="best", fontsize=7)
    for eje in planos[len(BARRIDOS):]:
        eje.set_visible(False)
    fig.suptitle("Sensibilidad de umbrales sobre escenarios sintéticos (semilla fija)", fontsize=13)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def _eje_x(barrido: Barrido) -> str:
    return "PERCLOS (%)" if barrido.parametro == "perclos_umbral" else "Valor del umbral"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=int, default=42, help="semilla del ruido sintético (def. 42)")
    parser.add_argument("--fps", type=int, default=15, help="fotogramas por segundo (def. 15)")
    parser.add_argument("--salida", type=Path, default=ROOT / "resultados",
                        help="directorio de salida (def. resultados/)")
    parser.add_argument("--parametros", default=",".join(b.parametro for b in BARRIDOS),
                        help="parámetros a barrer, separados por comas (def. todos)")
    args = parser.parse_args()

    if args.fps <= 0:
        parser.error("--fps debe ser positivo")
    nombres = [n.strip() for n in args.parametros.split(",") if n.strip()]
    disponibles = {b.parametro: b for b in BARRIDOS}
    desconocidos = [n for n in nombres if n not in disponibles]
    if desconocidos:
        parser.error(f"parámetros desconocidos: {desconocidos}. Opciones: {list(disponibles)}")
    barridos = [disponibles[n] for n in nombres]

    escenarios = sorted({c.escenario for b in barridos for c in b.casos} | {"normal"})
    desconocidos = [e for e in escenarios if e not in ESCENARIOS]
    if desconocidos:
        parser.error(f"escenarios desconocidos: {desconocidos}")

    args.salida.mkdir(parents=True, exist_ok=True)
    mediciones = {e: generar_mediciones(e, fps=args.fps, semilla=args.semilla) for e in escenarios}

    filas, detalles = [], []
    for barrido in barridos:
        for valor in barrido.valores:
            fila, det = evaluar_valor(barrido, valor, mediciones, args.fps)
            filas.append(fila)
            detalles.extend(det)
        print(f"[OK] {barrido.parametro:16s} {len(barrido.valores)} valores x "
              f"{len(barrido.casos)} casos -> {fila['detecciones']} con el valor final")

    salida = pd.DataFrame(filas)
    recomendaciones, notas = {}, {}
    for barrido in barridos:
        reco, nota = recomendar(barrido, salida[salida.parametro == barrido.parametro])
        recomendaciones[barrido.parametro] = (reco, nota)
        notas[barrido.parametro] = _impacto(
            barrido, salida[salida.parametro == barrido.parametro], reco)
    salida["valor_recomendado"] = salida.parametro.map(lambda p: recomendaciones[p][0])
    salida["es_recomendado"] = salida.apply(
        lambda r: bool(recomendaciones[r.parametro][0] is not None and
                       np.isclose(r.valor, recomendaciones[r.parametro][0])), axis=1)

    csv = args.salida / "sensibilidad_umbrales.csv"
    csv_det = args.salida / "sensibilidad_umbrales_detalles.csv"
    md = args.salida / "sensibilidad_umbrales.md"
    png = args.salida / "sensibilidad_umbrales.png"
    salida.to_csv(csv, index=False, encoding="utf-8-sig")
    pd.DataFrame(detalles).to_csv(csv_det, index=False, encoding="utf-8-sig")
    escribir_md(md, salida, recomendaciones, notas, args.semilla, args.fps, escenarios)
    graficar(png, salida, recomendaciones)
    for ruta in (csv, csv_det, md, png):
        print(f"[OK] {ruta}")
    for barrido in barridos:
        reco = recomendaciones[barrido.parametro][0]
        print(f"[REC] {barrido.parametro:16s} {_valor_texto(barrido, reco)}")


if __name__ == "__main__":
    main()
