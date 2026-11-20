---
name: driveguard-verificar-entorno
description: Verificar Python, dependencias, modelos, recursos y pruebas antes de trabajar en DriveGuardLab.
---

## Pasos

1. Confirmar Python 3.11 y el entorno `DriveGuardLab` desde la raíz del repo.
2. Comprobar los imports clave (`mediapipe`, `cv2`, `fastapi`, `streamlit`, `torch`) sin instalar nada; cualquier instalación se propone al estudiante.
3. Verificar `models/face_landmarker.task` y `assets/alarma_*.wav`. Si faltan, proponer `python scripts/descargar_modelos.py` y `python scripts/generar_recursos.py` (este último sobrescribe los CSV de ejemplo).
4. No leer `.env`: pedir al estudiante que revise la configuración. El estado real de MongoDB se consulta con `/health` cuando la API esté levantada.
5. Ejecutar `python -m pytest` y resumir fallos. No crear notebooks.
