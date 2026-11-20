---
name: driveguard-umbrales
description: Barrer umbrales del motor de riesgo y comparar detecciones contra falsas alarmas sin cambiar los defaults.
---

## Pasos

1. Identificar el parámetro a estudiar en `core/config.py` (`ConfigRiesgo`) y en la pestaña de configuración.
2. Crear `scripts/experimentos/<nombre>.py` con `argparse`, `--semilla` fija y `--salida resultados/`.
3. Barrer valores mediante `ConfigRiesgo.desde_dict(...)`; nunca editar los defaults ni `.env`.
4. Escribir CSV/PNG/MD en `resultados/` con detecciones, falsas alarmas y el valor recomendado.
5. Toda función nueva en `core/` lleva prueba en `tests/`. Ejecutar `python -m pytest` antes de entregar.
