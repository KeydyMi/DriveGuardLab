---
name: driveguard-cnn
description: Entrenar o evaluar la CNN opcional de ojos abiertos/cerrados con salida reproducible y sin exponer imágenes.
---

## Pasos

1. Pedir al estudiante que configure `OJOS_METODO=cnn`; no leer ni editar `.env`.
2. Usar el dataset local en `data/ojos/` (ignorado por Git) y `core/ojos_cnn.py`.
3. Crear `scripts/experimentos/<nombre>.py` con `argparse`, `--semilla` fija, `--dataset` y `--salida resultados/`; reportar F1 y matriz de confusión.
4. Guardar solo CSV/PNG/MD en `resultados/`; ninguna imagen de ojos o rostros en el repositorio.
5. No modificar los defaults de `ConfigRiesgo`; función nueva en `core/` implica prueba en `tests/`. Ejecutar `python -m pytest`.
