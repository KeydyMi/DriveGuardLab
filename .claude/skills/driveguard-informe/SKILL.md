---
name: driveguard-informe
description: Consolidar experimentos de resultados/ en un informe Markdown reproducible y listo para entrega.
---

## Pasos

1. Recopilar CSV/PNG/MD de `resultados/` y citar el comando y la semilla usados en cada experimento.
2. Verificar con `git status --short` que no haya notebooks nuevos ni imágenes/videos de rostros versionados.
3. Redactar el resumen en `resultados/<nombre>.md`, incluyendo hallazgos, limitaciones y el carácter académico del prototipo.
4. Ejecutar `python -m pytest` antes de darlo por terminado.
5. Proponer un commit pequeño con Conventional Commit en español; nunca hacer `git push` ni borrar ramas.
