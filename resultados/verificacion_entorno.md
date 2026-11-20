# Diagnóstico del entorno — DriveGuard Lab

Generado por `scripts/verificar_entorno.py` (sin instalar nada y sin leer `.env`).

| Chequeo | Estado | Detalle |
| --- | --- | --- |
| Python | OK | 3.11.18 (python.exe) |
| Entorno | AVISO | Entorno virtual '.venv' activo, no conda; se usan sus paquetes. conda no está en PATH. Se esperaba el entorno DriveGuardLab. |
| Import mediapipe | OK | 1.2.3 |
| Import cv2 | OK | 5.1.0 |
| Import fastapi | OK | 0.165.0 |
| Import streamlit | OK | 1.67.0 |
| Import torch | OK | 2.15.0+cpu |
| Modelo FaceLandmarker | OK | models/face_landmarker.task (3.8 MB) |
| Sonidos de alarma | OK | alarma_alta.wav (113 kB), alarma_media.wav (60 kB) |
| .env | AVISO | Presente; este script no lo lee ni lo imprime. Revise MONGO_URI, API_URL y NOTIFICACIONES_SIMULADAS en su terminal. |
| MongoDB localhost:27017 | OK | Puerto TCP 27017 abierto (el estado real se confirma con /health). |
| API /health | AVISO | API no levantada en 127.0.0.1:8000. Inicie: python -m uvicorn backend.main:app --reload --port 8000 |
| pytest | OK | código=0; 46 passed, 1 warning in 4.19s |

## Salida completa de pytest

```text
..............................................                           [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\D\OneDrive - Universidad Libre\Documents\DriveGuardLab\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
46 passed, 1 warning in 4.19s
```
