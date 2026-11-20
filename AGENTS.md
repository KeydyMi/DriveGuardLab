# AGENTS.md

Repo-specific notes for DriveGuardLab.

## Reglas del proyecto

1. No crear notebooks (`.ipynb`). Los experimentos son scripts en `scripts/experimentos/` con `argparse`, semilla fija y salida en `resultados/` (CSV, PNG, MD).
2. No cambiar los valores por defecto de `ConfigRiesgo` sin pedir confirmación.
3. No leer, imprimir ni modificar `.env`. Usar `NOTIFICACIONES_SIMULADAS=true` salvo que el estudiante pida un envío real.
4. No instalar `opencv-python-headless`; MediaPipe usa `opencv-contrib-python`.
5. Toda función nueva en `core/` lleva su prueba en `tests/`. Ejecutar `python -m pytest` antes de dar una tarea por terminada.
6. No hacer `git push` ni borrar ramas. Commits pequeños, Conventional Commits en español.
7. No guardar imágenes de rostros en el repositorio (`data/` está en `.gitignore`).

## Setup and commands

- Work from the repo root. Python 3.11; `environment.yml` names the conda env `DriveGuardLab` (the `driveguard` name in `README_ACTUALIZACION.md` is stale).
- Ask the student to prepare `.env` from `.env.example`; the agent never reads, prints, or edits it. Use `NOTIFICACIONES_SIMULADAS=true` unless a real send is requested. `.env` is loaded once in `core/config.py` at import — restart API/UI after the student changes it.
- Never install `opencv-python-headless`; MediaPipe needs `opencv-contrib-python` (`cv2` conflicts).
- Run API and UI in separate terminals:

  ```bat
  python -m uvicorn backend.main:app --reload --port 8000
  python -m streamlit run frontend/app.py
  ```

- Verify with `python -m pytest` (`pytest.ini`: `testpaths=tests`, `addopts=-q`). Focus examples: `python -m pytest tests/test_prevencion.py -q`, `python -m pytest tests/test_api.py::test_health -q`. Tests need no camera, model, or MongoDB: API tests inject `mongomock` via `storage.set_client(...)`, pipeline tests use a fake detector and `Alarma(backend="ninguno")`.
- FaceLandmarker auto-downloads on first camera use if online; preload with `python scripts/descargar_modelos.py` (`--vit` also fetches the ~350 MB expression model). Tests need neither.
- Do not casually rerun `python scripts/generar_recursos.py`: it regenerates `assets/*.wav` with `forzar=True` and always overwrites both `data/ejemplos/*.csv`.
- Notebook camera/audio/ViT/message cells are off by default via `USE_CAMERA`, `SONAR`, `USE_VIT`, `ENVIAR`; keep them off unless deliberately testing hardware.

## Structure and runtime

- `core/` is UI-agnostic logic; `backend/main.py` registers the API routers; `frontend/app.py` wires the 7 Streamlit tabs. Newer prevention/route work (`core/prevencion.py`, `backend/prevencion_api.py`, `frontend/prevencion_ui.py`, `frontend/recorridos_ui.py`, notebook 05) is documented only in `README_ACTUALIZACION.md`; `README.md` is stale there.
- Live monitoring uses separate threads: the streamlit-webrtc frame callback runs MediaPipe + risk + local alarm; the Streamlit UI polls state via `@st.fragment(run_every=0.5)`; the ViT is throttled in its own thread. Sound is played locally via pygame/winsound, not `st.audio`; don't call Streamlit APIs from the frame callback.
- MongoDB is optional at runtime (`/health` reports it; the UI warns). Emergency notifications fall back to local sending if the API is down.
- Most routers wrap DB calls in `backend.utils.ejecutar` (ValueError → 422, other errors → 503). `backend/prevencion_api.py` calls `storage.get_db()`/`storage._limpiar()` directly instead — don't copy that pattern for new endpoints unless you handle errors yourself.
- `/prevencion/evaluar` computes TTC only from measured distance plus positive relative speed; `velocidad_kmh` alone never yields a TTC. `/recorridos*` uses manually entered coordinates — no automatic GPS/sensor input.
