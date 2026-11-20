"""Experimento CNN de ojos abiertos/cerrados vs. regla del umbral EAR.

Genera el dataset SYNTHETICO en memoria (mismo generador del notebook 04),
entrena la arquitectura de `core.ojos_cnn` con semilla fija y compara F1,
matriz de confusión y ROC contra la regla `ear < ConfigRiesgo.ear_umbral_defecto`.

No se guardan imágenes de ojos/rostros, no se escribe en `models/`, no se lee
ni se edita `.env` directamente y **no se modifican los defaults de
`ConfigRiesgo`**: el umbral EAR se consulta, no se cambia.

Uso (dataset sintético, modo demostración):
    python scripts/experimentos/clasificador_ojos_cnn.py
    python scripts/experimentos/clasificador_ojos_cnn.py --semilla 7 --epocas 12

Uso con datos reales en `data/ojos/` (requiere EAR pareado en CSV):
    python scripts/experimentos/clasificador_ojos_cnn.py --dataset local \
        --ear-csv data/ojos/ears.csv

El CSV de EAR pareado debe tener columnas `archivo,ear` (nombre de archivo o
ruta relativa a `data/ojos/`). Los recortes se leen de `data/ojos/mrl/` y
`data/ojos/propios/{abiertos,cerrados}/`, como en el notebook 04.

Salida (solo CSV/PNG/MD, en resultados/):
    clasificador_ojos_cnn.csv            una fila por método (EAR y CNN)
    clasificador_ojos_cnn_predicciones.csv   una fila por muestra de prueba
    clasificador_ojos_cnn.png            matrices de confusión, ROC y entrenamiento
    clasificador_ojos_cnn.md             tablas, diferencias y limitaciones
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,  # noqa: E402
                             precision_score, recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import train_test_split  # noqa: E402

from core.config import OJOS_DIR, ROOT, ConfigRiesgo  # noqa: E402
from core.ojos_cnn import TAM, crear_cnn, preparar  # noqa: E402

NOMBRES_CLASES = ("cerrado", "abierto")  # 0 = cerrado, 1 = abierto (convención MRL)


def _rel(ruta: Path) -> str:
    """Ruta legible respecto a la raíz del repo (o absoluta si está fuera)."""
    try:
        return ruta.relative_to(ROOT).as_posix()
    except ValueError:
        return ruta.as_posix()


# --------------------------------------------------------------------------
# Datasets
# --------------------------------------------------------------------------
def generar_sinteticos(n: int, semilla: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Recortes 64x64 sintéticos con EAR pareado, sin escribir imágenes.

    Las formas copian el generador del notebook 04; los valores de EAR siguen
    las distribuciones del video sintético del proyecto (abierto ~0.30,
    cerrado ~0.06) para que la comparación sea pareada y reproducible.
    """
    rng = np.random.default_rng(semilla)
    recortes, etiquetas, ears = [], [], []
    for i in range(n):
        img = np.full((TAM, TAM), rng.integers(90, 170), np.uint8)
        img = np.clip(img + rng.normal(0, 12, img.shape), 0, 255).astype(np.uint8)
        cx, cy = TAM // 2 + rng.integers(-5, 6), TAM // 2 + rng.integers(-4, 5)
        if i % 2:  # abierto
            cv2.ellipse(img, (int(cx), int(cy)),
                        (int(rng.integers(18, 26)), int(rng.integers(8, 13))),
                        0, 0, 360, int(rng.integers(190, 240)), -1)
            cv2.circle(img, (int(cx + rng.integers(-4, 5)), int(cy)),
                       int(rng.integers(5, 8)), int(rng.integers(10, 60)), -1)
            ear = 0.30 + rng.normal(0, 0.008)
        else:      # cerrado
            cv2.ellipse(img, (int(cx), int(cy)),
                        (int(rng.integers(18, 26)), int(rng.integers(2, 5))),
                        0, 0, 180, int(rng.integers(20, 70)), 2)
            ear = 0.06 + abs(rng.normal(0, 0.006))
        recortes.append(cv2.GaussianBlur(img, (3, 3), 0))
        etiquetas.append(i % 2)
        ears.append(float(ear))
    return np.array(recortes), np.array(etiquetas), np.array(ears)


def cargar_local(carpeta: Path, ear_csv: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Carga MRL/capturas propias y su EAR medido en un CSV pareado."""
    if not ear_csv.exists():
        raise ValueError(f"No existe el CSV de EAR pareado: {ear_csv}")
    tabla = pd.read_csv(ear_csv)
    if not {"archivo", "ear"}.issubset(tabla.columns):
        raise ValueError("El CSV de EAR debe tener columnas `archivo,ear`")
    ears = dict(zip(tabla.archivo.astype(str), pd.to_numeric(tabla.ear, errors="coerce")))

    muestras: list[tuple[Path, int]] = []
    for ruta in (carpeta / "mrl").rglob("*.png"):
        partes = ruta.stem.split("_")
        if len(partes) >= 5 and partes[4] in ("0", "1"):
            muestras.append((ruta, int(partes[4])))
    for clase, nombre in enumerate(NOMBRES_CLASES):
        muestras += [(p, clase) for p in (carpeta / "propios" / f"{nombre}s").glob("*.png")]

    recortes, etiquetas, valores = [], [], []
    for ruta, clase in muestras:
        valor = ears.get(ruta.name, ears.get(ruta.relative_to(carpeta).as_posix()))
        if valor is None or pd.isna(valor):
            continue
        img = cv2.imread(str(ruta), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        recortes.append(cv2.resize(img, (TAM, TAM), interpolation=cv2.INTER_AREA))
        etiquetas.append(clase)
        valores.append(float(valor))
    if len(recortes) < 20:
        raise ValueError(f"Solo {len(recortes)} muestras con EAR pareado; se requieren ≥ 20")
    return np.array(recortes), np.array(etiquetas), np.array(valores)


# --------------------------------------------------------------------------
# Entrenamiento y evaluación
# --------------------------------------------------------------------------
def entrenar(recortes: np.ndarray, etiquetas: np.ndarray, semilla: int,
             epocas: int, lote: int) -> tuple[torch.nn.Module, list[dict]]:
    """Entrena `crear_cnn()` en CPU con orden de lotes determinista."""
    torch.manual_seed(semilla)
    random.seed(semilla)
    modelo = crear_cnn()
    optimizador = torch.optim.Adam(modelo.parameters(), lr=1e-3)
    perdida = torch.nn.CrossEntropyLoss()
    x = preparar(list(recortes))
    y = torch.as_tensor(etiquetas, dtype=torch.long)
    rng = np.random.default_rng(semilla)
    historial: list[dict] = []

    for epoca in range(1, epocas + 1):
        modelo.train()
        total = 0.0
        for inicio in range(0, len(y), lote):
            idx = torch.as_tensor(rng.permutation(len(y))[inicio:inicio + lote])
            optimizador.zero_grad()
            valor = perdida(modelo(x[idx]), y[idx])
            valor.backward()
            optimizador.step()
            total += valor.item() * len(idx)
        historial.append({"epoca": epoca, "perdida": total / len(y)})
    return modelo, historial


def predecir(modelo: torch.nn.Module, recortes: np.ndarray) -> np.ndarray:
    """Probabilidad de ojo cerrado (clase 0) para cada recorte."""
    modelo.eval()
    with torch.no_grad():
        return torch.softmax(modelo(preparar(list(recortes))), dim=1)[:, 0].numpy()


def metricas(y: np.ndarray, pred: int | np.ndarray, probabilidad: np.ndarray,
             umbral: float, metodo: str, origen: str, semilla: int) -> dict:
    """Métricas de la clase 'cerrado' (positiva) más F1 macro y AUC."""
    # Positivo = "cerrado" (clase 0). sklearn devuelve la matriz con positivo 1,
    # así que reordenamos explícitamente los cuatro recuentos.
    cerrado_bien, cerrado_como_abierto, abierto_como_cerrado, abierto_bien = confusion_matrix(
        y, pred, labels=[0, 1]).ravel()
    return {
        "metodo": metodo,
        "origen": origen,
        "semilla": semilla,
        "n_prueba": int(len(y)),
        "umbral": umbral,
        "exactitud": round(float(accuracy_score(y, pred)), 4),
        "precision_cerrado": round(float(precision_score(y, pred, pos_label=0, zero_division=0)), 4),
        "sensibilidad_cerrado": round(float(recall_score(y, pred, pos_label=0, zero_division=0)), 4),
        "f1_cerrado": round(float(f1_score(y, pred, pos_label=0, zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y, pred, average="macro", zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y, probabilidad)), 4),
        "tp": int(cerrado_bien), "tn": int(abierto_bien),
        "fp": int(abierto_como_cerrado), "fn": int(cerrado_como_abierto),
    }


# --------------------------------------------------------------------------
# Salidas
# --------------------------------------------------------------------------
def _celda_cm(cm: np.ndarray) -> str:
    return (f"| | Pred. cerrado | Pred. abierto |\n"
            f"| --- | --- | --- |\n"
            f"| Real cerrado | {cm[0, 0]} | {cm[0, 1]} |\n"
            f"| Real abierto | {cm[1, 0]} | {cm[1, 1]} |")


def escribir_md(ruta: Path, resumen: pd.DataFrame, historial: list[dict], args,
                origen: str, umbral_ear: float, comando: str) -> None:
    ear = resumen[resumen.metodo == "EAR"].iloc[0]
    cnn = resumen[resumen.metodo == "CNN"].iloc[0]
    lineas = [
        "# Clasificador CNN de ojos vs. umbral EAR",
        "",
        f"Reproducir: `{comando}`",
        "",
        f"- Origen de los datos: **{origen}**. Semilla `{args.semilla}`; "
        f"{int(ear.n_prueba)} muestras de prueba sobre las que se comparan ambos métodos.",
        f"- Umbral EAR usado: `{umbral_ear:g}` = `ConfigRiesgo().ear_umbral_defecto` "
        "(solo lectura; **los defaults no se modifican**). Umbral CNN: 0.50 sobre P(cerrado).",
        "- Convención: 0 = cerrado, 1 = abierto. EAR decide *cerrado* si `ear < umbral`; "
        "la CNN decide *cerrado* si `P(cerrado) > 0.5`.",
        f"- Entrenamiento: {args.epocas} épocas, lote {args.lote}, Adam lr=1e-3, CPU, "
        "semilla fija en numpy/torch. Modelo en memoria: **no se guarda en `models/`**.",
        "- `.env` no se leyó ni editó directamente; `OJOS_METODO` queda como estuviera "
        "(en esta ejecución se mantuvo `ear`). No se guardan imágenes de ojos/rostros.",
        "",
        "## Métricas comparativas",
        "",
        "| Método | Exactitud | Precisión (cerrado) | Sensibilidad (cerrado) | "
        "F1 cerrado | F1 macro | ROC AUC | TP | TN | FP | FN |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, r in resumen.iterrows():
        lineas.append(
            f"| {r.metodo} | {r.exactitud:.3f} | {r.precision_cerrado:.3f} | "
            f"{r.sensibilidad_cerrado:.3f} | **{r.f1_cerrado:.3f}** | {r.f1_macro:.3f} | "
            f"{r.roc_auc:.3f} | {r.tp} | {r.tn} | {r.fp} | {r.fn} |")
    lineas += [
        "",
        f"Diferencia F1 (CNN − EAR): **{cnn.f1_cerrado - ear.f1_cerrado:+.3f}** en la clase cerrado; "
        f"diferencia ROC AUC: **{cnn.roc_auc - ear.roc_auc:+.3f}**.",
        "",
        "## Matrices de confusión",
        "",
        "### EAR",
        "",
        _celda_cm(confusion_matrix_csv(resumen, "EAR")),
        "",
        "### CNN",
        "",
        _celda_cm(confusion_matrix_csv(resumen, "CNN")),
        "",
        "## Conclusión y alcance",
        "",
        "- Los dos métodos se miden sobre **las mismas muestras y la misma semilla**; "
        "la comparación es pareada.",
        "- Con datos sintéticos limpios ambas reglas pueden separar bien las clases: "
        "esto **no es evidencia** de rendimiento con conductores reales, iluminación "
        "variable, oclusión o cámaras infrarrojas.",
        "- Para una conclusión válida, repetir con `--dataset local` y EAR medido con "
        "MediaPipe en `data/ojos/`, y validar en video etiquetado antes de pensar en "
        "activar `OJOS_METODO=cnn`.",
        "",
    ]
    if historial:
        lineas += ["## Entrenamiento", "",
                   "| Época | Pérdida media |", "| --- | --- |"]
        lineas += [f"| {h['epoca']} | {h['perdida']:.4f} |" for h in historial]
        lineas.append("")
    ruta.write_text("\n".join(lineas), encoding="utf-8")


def confusion_matrix_csv(resumen: pd.DataFrame, metodo: str) -> np.ndarray:
    """Reconstruye la matriz 2x2 (filas=real, columnas=pred) con positivo 'cerrado'."""
    r = resumen[resumen.metodo == metodo].iloc[0]
    return np.array([[r.tp, r.fn], [r.fp, r.tn]])


def graficar(ruta: Path, resumen: pd.DataFrame, historial: list[dict],
             y: np.ndarray, scores: dict[str, np.ndarray], origen: str) -> None:
    fig, ejes = plt.subplots(1, 4, figsize=(18, 4.2))
    for eje, metodo in zip(ejes[:2], ("EAR", "CNN")):
        r = resumen[resumen.metodo == metodo].iloc[0]
        cm = confusion_matrix_csv(resumen, metodo)
        eje.imshow(cm, cmap="Blues", vmin=0)
        for (i, j), valor in np.ndenumerate(cm):
            eje.text(j, i, str(valor), ha="center", va="center",
                     color="white" if valor > cm.max() / 2 else "black")
        eje.set_xticks([0, 1], NOMBRES_CLASES)
        eje.set_yticks([0, 1], NOMBRES_CLASES)
        eje.set_title(f"{metodo} — F1 cerrado {r.f1_cerrado:.3f}")
        eje.set_xlabel("Predicción")
        eje.set_ylabel("Real")
    for metodo, score in scores.items():
        fpr, tpr, _ = roc_curve(y, score)
        ejes[2].plot(fpr, tpr, label=f"{metodo} (AUC={roc_auc_score(y, score):.3f})")
    ejes[2].plot([0, 1], [0, 1], "k:", lw=1)
    ejes[2].set(xlabel="Tasa de falsos positivos", ylabel="Tasa de verdaderos positivos",
                title="ROC (clase abierto)")
    ejes[2].legend(loc="lower right", fontsize=9)
    ejes[2].grid(alpha=0.25)
    if historial:
        ejes[3].plot([h["epoca"] for h in historial], [h["perdida"] for h in historial], "o-")
        ejes[3].set(xlabel="Época", ylabel="Pérdida media", title="Entrenamiento")
        ejes[3].grid(alpha=0.25)
    else:
        ejes[3].set_visible(False)
    fig.suptitle(f"CNN de ojos vs. EAR — {origen}")
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--semilla", type=int, default=42, help="semilla fija (def. 42)")
    parser.add_argument("--dataset", choices=("sintetico", "local"), default="sintetico",
                        help="origen de los recortes (def. sintetico, modo demostración)")
    parser.add_argument("--n-muestras", type=int, default=1500,
                        help="nº de recortes sintéticos (def. 1500)")
    parser.add_argument("--epocas", type=int, default=10, help="épocas de entrenamiento (def. 10)")
    parser.add_argument("--lote", type=int, default=64, help="tamaño de lote (def. 64)")
    parser.add_argument("--ear-csv", type=Path, default=None,
                        help="CSV archivo,ear con EAR medido (obligatorio con --dataset local)")
    parser.add_argument("--salida", type=Path, default=ROOT / "resultados",
                        help="directorio de salida (def. resultados/)")
    args = parser.parse_args()

    if args.n_muestras < 100:
        parser.error("--n-muestras debe ser ≥ 100")
    if args.epocas < 1 or args.lote < 1:
        parser.error("--epocas y --lote deben ser positivos")
    if args.dataset == "local" and args.ear_csv is None:
        parser.error("--dataset local requiere --ear-csv con columnas archivo,ear")

    torch.set_num_threads(1)  # reproducibilidad en CPU
    if args.dataset == "sintetico":
        recortes, etiquetas, ears = generar_sinteticos(args.n_muestras, args.semilla)
        origen = "SINTÉTICO (demo: no válido como evidencia real)"
    else:
        recortes, etiquetas, ears = cargar_local(OJOS_DIR, args.ear_csv)
        origen = f"local: {OJOS_DIR.relative_to(ROOT).as_posix()} + {args.ear_csv.name}"

    x_tr, x_te, y_tr, y_te, ear_tr, ear_te = train_test_split(
        recortes, etiquetas, ears, test_size=0.2, stratify=etiquetas,
        random_state=args.semilla)
    x_tr, x_va, y_tr, y_va, _, _ = train_test_split(
        x_tr, y_tr, ear_tr, test_size=0.15, stratify=y_tr,
        random_state=args.semilla)

    modelo, historial = entrenar(x_tr, y_tr, args.semilla, args.epocas, args.lote)
    p_cerrado = predecir(modelo, x_te)
    umbral_ear = float(ConfigRiesgo().ear_umbral_defecto)  # solo lectura
    # Convención de clases: 0 = cerrado, 1 = abierto.
    pred_ear = (ear_te >= umbral_ear).astype(int)        # EAR bajo => cerrado
    pred_cnn = (p_cerrado <= 0.5).astype(int)            # P(cerrado) alta => cerrado

    # Score de ROC siempre con positivo = "abierto" (clase 1).
    resumen = pd.DataFrame([
        metricas(y_te, pred_ear, ear_te, umbral_ear, "EAR", origen, args.semilla),
        metricas(y_te, pred_cnn, 1.0 - p_cerrado, 0.5, "CNN", origen, args.semilla),
    ])
    predicciones = pd.DataFrame({
        "indice": np.arange(len(y_te)),
        "etiqueta_real": y_te,
        "ear": np.round(ear_te, 5),
        "p_cerrado_cnn": np.round(p_cerrado, 5),
        "prediccion_ear": pred_ear,
        "prediccion_cnn": pred_cnn,
        "acierto_ear": (pred_ear == y_te).astype(int),
        "acierto_cnn": (pred_cnn == y_te).astype(int),
    })

    args.salida.mkdir(parents=True, exist_ok=True)
    ruta_csv = args.salida / "clasificador_ojos_cnn.csv"
    ruta_pred = args.salida / "clasificador_ojos_cnn_predicciones.csv"
    ruta_png = args.salida / "clasificador_ojos_cnn.png"
    ruta_md = args.salida / "clasificador_ojos_cnn.md"
    resumen.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    predicciones.to_csv(ruta_pred, index=False, encoding="utf-8-sig")

    comando = (f"python scripts/experimentos/clasificador_ojos_cnn.py --semilla {args.semilla} "
               f"--dataset {args.dataset} --epocas {args.epocas} --lote {args.lote} "
               f"--salida {_rel(args.salida)}")
    if args.dataset == "sintetico":
        comando += f" --n-muestras {args.n_muestras}"
    if args.ear_csv is not None:
        comando += f" --ear-csv {args.ear_csv.as_posix()}"
    escribir_md(ruta_md, resumen, historial, args, origen, umbral_ear, comando)
    graficar(ruta_png, resumen, historial, y_te,
             {"EAR": ear_te, "CNN": 1.0 - p_cerrado}, origen)
    for ruta in (ruta_csv, ruta_pred, ruta_png, ruta_md):
        print(f"[OK] {_rel(ruta)}")
    for _, r in resumen.iterrows():
        print(f"[MET] {r.metodo:3s} F1_cerrado={r.f1_cerrado:.3f} "
              f"F1_macro={r.f1_macro:.3f} AUC={r.roc_auc:.3f} "
              f"TP={r.tp} TN={r.tn} FP={r.fp} FN={r.fn}")


if __name__ == "__main__":
    main()
