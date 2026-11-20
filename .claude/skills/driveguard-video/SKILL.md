---
name: driveguard-video
description: Analizar un video grabado con el pipeline de DriveGuardLab sin usar cámara ni guardar fotogramas con rostros.
---

## Pasos

1. Usar un video ya grabado; no iniciar `streamlit-webrtc` ni la cámara.
2. Crear `scripts/experimentos/<nombre>.py` con `argparse` (`--video`, `--semilla`, `--salida resultados/`) y ejecutar `core.pipeline.ProcesadorConductor` sobre el video.
3. Guardar métricas y gráficas como CSV/PNG/MD en `resultados/`; no versionar fotogramas ni MP4 con rostros (`resultados/*.mp4` está ignorado).
4. No cambiar los defaults de `ConfigRiesgo` ni crear notebooks.
5. Si se añade código en `core/`, agregar la prueba correspondiente en `tests/` y ejecutar `python -m pytest`.
