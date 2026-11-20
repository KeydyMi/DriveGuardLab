---
name: driveguard-escenarios
description: Generar escenarios sintéticos de somnolencia y distracción con semilla fija y salida reproducible.
---

## Pasos

1. Definir el escenario (microsueño, PERCLOS, bostezos, cabeceo o distracción) reutilizando `core.simulacion` y `core.riesgo`.
2. Crear el experimento como `scripts/experimentos/<nombre>.py` con `argparse`, `--semilla` fija y `--salida resultados/`.
3. Guardar solo CSV/MD (y PNG si aplica) en `resultados/`; no guardar imágenes de rostros ni notebooks.
4. No modificar los valores por defecto de `ConfigRiesgo`; usar `ConfigRiesgo.desde_dict` para pruebas temporales.
5. Si se añade una función en `core/`, crear su prueba en `tests/`; ejecutar `python -m pytest` antes de terminar.
