"""Evaluación del pipeline sobre un video, sin cámara ni streamlit-webrtc.

Uso:
    python scripts/experimentos/evaluacion_video.py
    python scripts/experimentos/evaluacion_video.py --semilla 7 --fps 15 --salida resultados
    python scripts/experimentos/evaluacion_video.py --video data/videos/mi_video.mp4
    python scripts/experimentos/evaluacion_video.py --generar

Si no existe video en `data/videos/`, se genera uno sintético a partir del
retrato de muestra que trae matplotlib. Ese retrato solo sirve de fondo: el
detector real de MediaPipe se ejecuta en cada fotograma (para medir latencia),
pero EAR/MAR se sustituyen por una señal sintética con semilla fija para
reproducir parpadeos, microsueño, bostezos y rostro ausente. El motor de
riesgo, los eventos y el dibujo son los del proyecto, sin cambios. Si se pasa
un video propio, se usa el detector real sin inyectar métricas.

Salida (solo CSV/PNG/MD en resultados/):
    evaluacion_video_fotogramas.csv   una fila por fotograma procesado
    evaluacion_video_resumen.csv      una fila con rendimiento y detecciones
    evaluacion_video.png              gráficas de EAR/MAR, nivel y latencia
    evaluacion_video.md               resumen reproducible

No se guardan fotogramas ni videos anotados: `data/` y `resultados/*.mp4`
están ignorados por Git. No se lee `.env` ni se cambian los defaults de
`ConfigRiesgo`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.cbook import get_sample_data  # noqa: E402

from core.config import ROOT, VIDEOS_DIR, ConfigRiesgo  # noqa: E402
from core.landmarks import DetectorRostro  # noqa: E402
from core.pipeline import ProcesadorConductor  # noqa: E402
from core.riesgo import ORDEN  # noqa: E402

VIDEO_POR_DEFECTO = VIDEOS_DIR / "sintetico_somnolencia.mp4"
MANIFIESTO_POR_DEFECTO = VIDEO_POR_DEFECTO.with_suffix(".json")
FPS_DEFECTO = 15
DURACION_DEFECTO = 50.0
FUENTE_RETRATO = "matplotlib:grace_hopper.jpg"

# (inicio_s, fin_s, fase, descripción)
FASES: tuple[tuple[float, float, str, str], ...] = (
    (0.0, 11.0, "normal", "Parpadeos normales; calibración de 10 s"),
    (11.0, 16.0, "normal", "Conducción estable"),
    (16.0, 19.0, "microsueno", "Ojos cerrados 3 s"),
    (19.0, 24.0, "normal", "Recuperación"),
    (24.0, 27.5, "bostezo", "Bostezo 1"),
    (27.5, 30.0, "normal", "Recuperación"),
    (30.0, 33.5, "bostezo", "Bostezo 2"),
    (33.5, 36.0, "normal", "Recuperación"),
    (36.0, 39.5, "bostezo", "Bostezo 3"),
    (39.5, 41.0, "normal", "Recuperación"),
    (41.0, 47.0, "rostro_ausente", "Rostro fuera de cámara 6 s"),
    (47.0, DURACION_DEFECTO, "normal", "Recuperación final"),
)
MOTIVOS = ("microsueno", "bostezos", "rostro_ausente", "cansancio_perclos",
           "distraccion", "cabeza_caida", "cabeceos")


# --------------------------------------------------------------------------
# Video sintético (queda solo en data/videos/, ignorado por Git)
# --------------------------------------------------------------------------
def generar_video_sintetico(destino: Path, semilla: int, fps: int,
                            duracion: float) -> dict:
    """Crea un video con un retrato de muestra y movimiento determinista."""
    rng = np.random.default_rng(semilla)
    ancho, alto = 640, 480
    with get_sample_data("grace_hopper.jpg") as archivo:
        retrato = cv2.imdecode(np.frombuffer(archivo.read(), np.uint8), cv2.IMREAD_COLOR)
    if retrato is None:
        raise ValueError("No se pudo leer el retrato de muestra de matplotlib")

    escala = min((alto - 30) / retrato.shape[0], (ancho - 40) / retrato.shape[1])
    retrato = cv2.resize(retrato, None, fx=escala, fy=escala)
    h, w = retrato.shape[:2]
    x0, y0 = (ancho - w) // 2, (alto - h) // 2
    fondo = np.zeros((alto, ancho, 3), np.uint8)
    for fila in range(alto):
        fondo[fila, :, :] = (45 + int(20 * fila / alto), 50 + int(18 * fila / alto),
                             58 + int(15 * fila / alto))
    cv2.putText(fondo, "VIDEO SINTETICO - DriveGuardLab", (12, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)

    destino.parent.mkdir(parents=True, exist_ok=True)
    escritor = cv2.VideoWriter(str(destino), cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto))
    if not escritor.isOpened():
        raise ValueError(f"No se pudo crear el video sintético {destino}")
    try:
        for i in range(int(duracion * fps)):
            t = i / fps
            dx = int(3 * np.sin(2 * np.pi * t / 7 + semilla))
            dy = int(2 * np.sin(2 * np.pi * t / 5 + semilla / 3))
            frame = fondo.copy()
            frame[y0 + dy:y0 + dy + h, x0 + dx:x0 + dx + w] = retrato
            brillo = 1.0 + rng.normal(0, 0.012)
            frame = cv2.convertScaleAbs(frame, alpha=brillo, beta=0)
            escritor.write(frame)
    finally:
        escritor.release()

    manifiesto = {"video": destino.name, "semilla": semilla, "fps": fps,
                  "duracion_s": duracion, "fuente": FUENTE_RETRATO,
                  "fases": [list(f) for f in FASES]}
    destino.with_suffix(".json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifiesto


# --------------------------------------------------------------------------
# Detector: MediaPipe real + señal fisiológica sintética
# --------------------------------------------------------------------------
class DetectorVideoSintetico:
    """Ejecuta MediaPipe en cada frame y sustituye EAR/MAR por la señal del guion.

    Así se ejercita el pipeline completo (detección de rostro, latencia de
    MediaPipe, motor de riesgo, eventos y dibujo) sin grabar a una persona ni
    guardar imágenes con rostros.
    """

    def __init__(self, semilla: int):
        self.detector = DetectorRostro(modo="video")
        self.rng = np.random.default_rng(semilla + 1000)
        self.ultima_latencia_ms = 0.0
        self.fase = "normal"

    @staticmethod
    def _fase_en(t: float) -> str:
        for ini, fin, nombre, _ in FASES:
            if ini <= t < fin:
                return nombre
        return "normal"

    def parametros(self, t: float) -> tuple[float, float, bool]:
        """Devuelve (EAR, MAR, rostro_visible) para el instante `t`."""
        fase = self._fase_en(t)
        ear = 0.30 + self.rng.normal(0, 0.008)
        mar = max(0.01, 0.05 + self.rng.normal(0, 0.012))
        visible = True
        if fase == "microsueno":
            ear = 0.06 + abs(self.rng.normal(0, 0.006))
        elif fase == "bostezo":
            mar = 0.85 + abs(self.rng.normal(0, 0.03))
        elif fase == "rostro_ausente":
            visible = False
        elif t % 4.0 < 0.13:           # parpadeo normal fuera del microsueño
            ear = 0.10 + abs(self.rng.normal(0, 0.008))
        return float(ear), float(mar), visible

    def procesar(self, frame: np.ndarray, t_ms: int | None = None):
        t = 0.0 if t_ms is None else t_ms / 1000.0
        self.fase = self._fase_en(t)
        ear, mar, visible = self.parametros(t)
        entrada = frame
        if not visible:
            entrada = np.full_like(frame, 58)   # rostro fuera de campo: sin rostro
        inicio = time.perf_counter()
        rostro = self.detector.procesar(entrada, t_ms)
        self.ultima_latencia_ms = (time.perf_counter() - inicio) * 1000
        if rostro is not None and visible:
            rostro.ear = rostro.ear_izq = rostro.ear_der = ear
            rostro.mar = mar
            rostro.pitch = 0.0
            rostro.yaw = 0.0
        return rostro

    def cerrar(self) -> None:
        self.detector.cerrar()


# --------------------------------------------------------------------------
# Procesamiento y métricas
# --------------------------------------------------------------------------
def procesar_video(video: Path, salida: Path, semilla: int, fps: int,
                   duracion: float, sintetico: bool) -> tuple[pd.DataFrame, pd.DataFrame, list[dict], dict]:
    """Recorre el video con `ProcesadorConductor` y devuelve métricas y eventos."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video {video}")
    detector = DetectorVideoSintetico(semilla) if sintetico else DetectorRostro(modo="video")
    proc = ProcesadorConductor(config=ConfigRiesgo(), expresiones=False, alarma=False,
                               detector=detector, metodo_ojos="ear", intervalo_muestra_s=2.0)
    filas: list[dict] = []
    i = 0
    inicio_total = time.perf_counter()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = i / fps
            inicio = time.perf_counter()
            _, estado = proc.procesar(frame, t=t)
            latencia_ms = (time.perf_counter() - inicio) * 1000
            filas.append({
                "t": round(t, 3),
                "fase": detector.fase if sintetico else "video_propio",
                "nivel": estado.nivel,
                "motivos": ",".join(estado.motivos),
                "ear": estado.ear,
                "ear_umbral": estado.ear_umbral,
                "mar": estado.mar,
                "perclos": estado.perclos,
                "ojos_cerrados": estado.ojos_cerrados,
                "tiempo_ojos_cerrados": estado.tiempo_ojos_cerrados,
                "bostezos": estado.bostezos,
                "rostro": estado.rostro,
                "calibrando": estado.calibrando,
                "emergencia": estado.emergencia,
                "latencia_ms": round(latencia_ms, 3),
                "deteccion_ms": round(detector.ultima_latencia_ms, 3),
                "fps_instante": round(1000.0 / latencia_ms, 2) if latencia_ms else None,
            })
            i += 1
            if duracion and t >= duracion:
                break
    finally:
        cap.release()
        proc.cerrar()
    elapsed = time.perf_counter() - inicio_total
    eventos = proc.extraer_eventos()

    df = pd.DataFrame(filas)
    if df.empty:
        raise ValueError(f"No se pudieron leer fotogramas de {video}")
    lat = df.latencia_ms.to_numpy()
    post = df[~df.calibrando]
    resumen = {
        "video": str(video.relative_to(ROOT)) if video.is_relative_to(ROOT) else str(video),
        "semilla": semilla,
        "video_sintetico": sintetico,
        "fps_video": fps,
        "frames": int(len(df)),
        "duracion_s": round(float(df.t.iloc[-1] + 1 / fps), 2),
        "tiempo_total_s": round(elapsed, 3),
        "fps_flujo": round(len(df) / elapsed, 2) if elapsed else None,
        "fps_procesamiento": round(1000.0 / float(lat.mean()), 2) if lat.mean() else None,
        "latencia_media_ms": round(float(lat.mean()), 2),
        "latencia_p50_ms": round(float(np.percentile(lat, 50)), 2),
        "latencia_p95_ms": round(float(np.percentile(lat, 95)), 2),
        "latencia_max_ms": round(float(lat.max()), 2),
        "deteccion_media_ms": round(float(df.deteccion_ms.mean()), 2),
        "frames_rostro": int(df.rostro.sum()),
        "frames_calibracion": int(df.calibrando.sum()),
        "nivel_max": max(df.nivel, key=lambda n: ORDEN[n]),
        "s_normal": round(int((post.nivel == "NORMAL").sum()) / fps, 2),
        "s_bajo": round(int((post.nivel == "BAJO").sum()) / fps, 2),
        "s_medio": round(int((post.nivel == "MEDIO").sum()) / fps, 2),
        "s_alto": round(int((post.nivel == "ALTO").sum()) / fps, 2),
        "cambios_nivel": sum(e["tipo"] != "muestra" for e in eventos),
        "muestras": sum(e["tipo"] == "muestra" for e in eventos),
        "frames_emergencia": int(df.emergencia.sum()),
    }
    for motivo in MOTIVOS:
        filas_motivo = df[df.motivos.str.contains(motivo, regex=False)]
        resumen[f"primera_{motivo}_s"] = (round(float(filas_motivo.t.iloc[0]), 2)
                                         if not filas_motivo.empty else None)
        resumen[f"frames_{motivo}"] = int(len(filas_motivo))
    return df, pd.DataFrame([resumen]), eventos, {"elapsed": elapsed}


# --------------------------------------------------------------------------
# Informes
# --------------------------------------------------------------------------
def graficar(ruta: Path, df: pd.DataFrame) -> None:
    """Gráficas de métricas; no contienen imágenes de rostros."""
    fig, ejes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    ejes[0].plot(df.t, df.ear, lw=1, color="#1f77b4", label="EAR")
    ejes[0].plot(df.t, df.ear_umbral, lw=1.2, ls="--", color="#d62728", label="Umbral EAR")
    ejes[0].set_ylabel("EAR")
    ejes[0].legend(loc="upper right", fontsize=8)
    ejes[0].grid(alpha=0.25)

    colores = {"NORMAL": "#2ca02c", "BAJO": "#17becf", "MEDIO": "#ff7f0e", "ALTO": "#d62728"}
    ejes[1].plot(df.t, df.mar, lw=1, color="#7b3294", label="MAR")
    for nivel, color in colores.items():
        sel = df[df.nivel == nivel]
        if not sel.empty:
            ejes[1].scatter(sel.t, np.full(len(sel), 1.05), s=3, color=color, label=nivel)
    ejes[1].axhline(ConfigRiesgo().mar_umbral, ls=":", color="0.4", lw=1, label="Umbral MAR")
    ejes[1].set_ylim(-0.05, 1.2)
    ejes[1].set_ylabel("MAR / nivel")
    ejes[1].legend(loc="upper left", fontsize=8, ncol=5)
    ejes[1].grid(alpha=0.25)

    ejes[2].hist(df.latencia_ms, bins=40, color="#4c72b0", edgecolor="white")
    ejes[2].axvline(df.latencia_ms.median(), color="#2ca02c", ls="--",
                    label=f"p50 {df.latencia_ms.median():.1f} ms")
    ejes[2].axvline(np.percentile(df.latencia_ms, 95), color="#d62728", ls="--",
                    label=f"p95 {np.percentile(df.latencia_ms, 95):.1f} ms")
    ejes[2].set_xlabel("Tiempo del video (s) / latencia por fotograma (ms)")
    ejes[2].set_ylabel("Fotogramas")
    ejes[2].legend(fontsize=8)
    ejes[2].grid(alpha=0.25)
    fig.suptitle("Evaluación del pipeline sobre video (métricas, no fotogramas)")
    fig.tight_layout()
    fig.savefig(ruta, dpi=140)
    plt.close(fig)


def escribir_md(ruta: Path, res: pd.DataFrame, df: pd.DataFrame, eventos: list[dict],
                video: Path, semilla: int, fps: int, sintetico: bool,
                manifiesto: dict | None) -> None:
    r = res.iloc[0]
    cfg = ConfigRiesgo()
    comando = ("python scripts/experimentos/evaluacion_video.py "
               f"--video {video.relative_to(ROOT) if video.is_relative_to(ROOT) else video} "
               f"--semilla {semilla} --fps {fps} --salida {ruta.parent.relative_to(ROOT)}")
    lineas = [
        "# Evaluación del pipeline sobre video grabado",
        "",
        f"Reproducir: `{comando}`",
        "",
        f"- Video: `{video.relative_to(ROOT) if video.is_relative_to(ROOT) else video}` "
        f"({'sintético' if sintetico else 'propio'}); semilla `{semilla}`; "
        f"`{fps}` fps del video.",
        "- Sin cámara, sin `streamlit-webrtc` y sin guardar fotogramas: solo CSV/PNG/MD "
        "en `resultados/`. No se lee `.env`.",
        f"- `ConfigRiesgo()` sin cambios (calibración {cfg.calibracion_s:g} s, factor EAR "
        f"{cfg.factor_ear:g}, microsueño {cfg.microsueno_s:g} s, MAR {cfg.mar_umbral:g}, "
        f"{cfg.bostezos_limite} bostezos/{cfg.bostezo_ventana_s / 60:g} min, "
        f"histéresis {cfg.histeresis_s:g} s).",
    ]
    if sintetico:
        lineas += [
            f"- Retrato de muestra `{FUENTE_RETRATO}` usado solo como fondo. MediaPipe se ejecuta "
            "en cada fotograma para medir latencia real; EAR/MAR se sustituyen por una señal "
            "determinista (semilla fija) porque las ediciones del retrato no cambian los "
            "landmarks del modelo. Motor de riesgo y eventos: código original del proyecto.",
        ]
        if manifiesto:
            lineas += ["", "## Guion del video sintético", "",
                       "| Fase | Intervalo (s) | Descripción |", "| --- | --- | --- |"]
            for ini, fin, _, descripcion in FASES:
                lineas.append(f"| {ini:g}–{fin:g} | {fin - ini:g} | {descripcion} |")
    lineas += [
        "", "## Rendimiento", "",
        "| Métrica | Valor |", "| --- | --- |",
        f"| Fotogramas procesados | {int(r.frames)} |",
        f"| Duración del video | {r.duracion_s:.2f} s |",
        f"| Tiempo total (lectura + procesamiento) | {r.tiempo_total_s:.2f} s |",
        f"| FPS de flujo (frames / tiempo total) | {r.fps_flujo:.2f} |",
        f"| FPS de procesamiento (1 / latencia media) | {r.fps_procesamiento:.2f} |",
        f"| Latencia media / p50 / p95 / máx | {r.latencia_media_ms:.1f} / "
        f"{r.latencia_p50_ms:.1f} / {r.latencia_p95_ms:.1f} / {r.latencia_max_ms:.1f} ms |",
        f"| Latencia media de MediaPipe | {r.deteccion_media_ms:.1f} ms |",
        f"| Fotogramas con rostro | {int(r.frames_rostro)} / {int(r.frames)} |",
        "",
        "La latencia es tiempo de reloj de pared: depende del equipo. El FPS del pipeline "
        "calculado con `t` del video sería el `fps_video`; aquí se reporta el rendimiento real.",
        "", "## Detecciones", "",
        "| Motivo | Primera aparición | Fotogramas | Nivel máx. |",
        "| --- | --- | --- | --- |",
    ]
    for motivo in MOTIVOS:
        primera = r[f"primera_{motivo}_s"]
        if pd.isna(primera):
            continue
        seleccion = df[df.motivos.str.contains(motivo, regex=False)]
        nivel_max = max(seleccion.nivel, key=lambda n: ORDEN[n])
        lineas.append(f"| {motivo} | {primera:.2f} s | {int(r[f'frames_{motivo}'])} | {nivel_max} |")
    lineas += [
        "",
        f"Nivel máximo global: **{r.nivel_max}**. Tiempos tras la calibración: "
        f"NORMAL {r.s_normal:.1f} s, BAJO {r.s_bajo:.1f} s, "
        f"MEDIO {r.s_medio:.1f} s, ALTO {r.s_alto:.1f} s.",
        f"Eventos: {int(r.cambios_nivel)} cambios de nivel y {int(r.muestras)} muestras "
        f"periódicas; fotogramas en emergencia: {int(r.frames_emergencia)}.",
        "", "### Eventos de cambio de nivel", "",
        "| t (s) | Nivel | Anterior | Motivo |", "| --- | --- | --- | --- |",
    ]
    for ev in [e for e in eventos if e["tipo"] != "muestra"][:20]:
        motivos = ", ".join(ev["motivos"]) or "—"
        lineas.append(f"| {ev['t_s']:.2f} | {ev['nivel']} | {ev['nivel_anterior']} | {motivos} |")
    lineas += [
        "",
        "Nota: con un solo video no se calculan sensibilidad ni falsas alarmas; esas "
        "métricas se cubren en `sensibilidad_umbrales.md` con escenarios de verdad conocida.",
        "",
    ]
    ruta.write_text("\n".join(lineas), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, default=VIDEO_POR_DEFECTO,
                        help=f"video a evaluar (def. {VIDEO_POR_DEFECTO.relative_to(ROOT)})")
    parser.add_argument("--semilla", type=int, default=42, help="semilla sintética (def. 42)")
    parser.add_argument("--salida", type=Path, default=ROOT / "resultados",
                        help="directorio de salida (def. resultados/)")
    parser.add_argument("--fps", type=int, default=FPS_DEFECTO, help="fps del video (def. 15)")
    parser.add_argument("--duracion", type=float, default=DURACION_DEFECTO,
                        help="duración máxima a procesar en segundos (def. 50)")
    parser.add_argument("--generar", action="store_true",
                        help="regenerar el video sintético aunque ya exista")
    args = parser.parse_args()

    if args.fps <= 0 or args.duracion <= 0:
        parser.error("--fps y --duracion deben ser positivos")
    args.salida.mkdir(parents=True, exist_ok=True)

    video = args.video
    es_defecto = video.resolve() == VIDEO_POR_DEFECTO.resolve()
    manifiesto_path = (MANIFIESTO_POR_DEFECTO if es_defecto
                       else video.with_suffix(".json"))
    if args.generar or not video.exists():
        if not es_defecto:
            parser.error("--generar solo aplica al video sintético por defecto")
        print(f"[INFO] No hay video de prueba; generando {video.relative_to(ROOT).as_posix()} ...")
        manifiesto = generar_video_sintetico(video, args.semilla, args.fps, args.duracion)
    else:
        manifiesto = (json.loads(manifiesto_path.read_text(encoding="utf-8"))
                      if manifiesto_path.exists() else None)
    sintetico = manifiesto is not None
    if sintetico:
        args.fps = int(manifiesto["fps"])
        args.duracion = float(manifiesto["duracion_s"])
        args.semilla = int(manifiesto["semilla"])
        print(f"[INFO] Video sintetico con guion: semilla {args.semilla}, "
              f"{args.fps} fps, {args.duracion:g} s")
    else:
        print("[INFO] Video propio: deteccion real, sin inyeccion de EAR/MAR")

    df, res, eventos, _ = procesar_video(video, args.salida, args.semilla, args.fps,
                                         args.duracion, sintetico)
    csv_frames = args.salida / "evaluacion_video_fotogramas.csv"
    csv_res = args.salida / "evaluacion_video_resumen.csv"
    png = args.salida / "evaluacion_video.png"
    md = args.salida / "evaluacion_video.md"
    df.to_csv(csv_frames, index=False, encoding="utf-8-sig")
    res.to_csv(csv_res, index=False, encoding="utf-8-sig")
    graficar(png, df)
    escribir_md(md, res, df, eventos, video, args.semilla, args.fps, sintetico, manifiesto)

    r = res.iloc[0]
    print(f"[OK] {int(r.frames)} fotogramas en {r.tiempo_total_s:.2f} s "
          f"({r.fps_flujo:.1f} FPS de flujo, {r.fps_procesamiento:.1f} FPS de procesamiento)")
    print(f"[OK] Latencia media/p95: {r.latencia_media_ms:.1f}/{r.latencia_p95_ms:.1f} ms; "
          f"nivel max. {r.nivel_max}")
    for ruta in (csv_frames, csv_res, png, md):
        print(f"[OK] {ruta}")


if __name__ == "__main__":
    main()
