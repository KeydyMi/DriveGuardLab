# Bitácora Agéntica — DriveGuard Lab

- **Estudiantes:** Eblin Doriana Aviles Keydy Michelle Avilés 
- **Rama:** `lab/diaz-keydy`
- **Consola utilizada:** OpenCode (modo Plan y Build)

---

## Fase 1: Preparación del entorno agéntico y exploración arquitectónica

### 1. Mapa de módulos del sistema
- **`core/`**: Lógica pura del dominio sin dependencias de UI ni red: configuración y umbrales (`config.py`), detección facial de 478 puntos y métricas EAR/MAR/cabeceo con MediaPipe (`landmarks.py`), clasificadores opcionales (`ojos_cnn.py`, `faces.py`), máquina de estados de fatiga (`riesgo.py`), orquestación por fotograma (`pipeline.py`), alarma sonora en hilo independiente (`alarma.py`), notificaciones simuladas/reales (`notificaciones.py`), persistencia en MongoDB (`storage.py`), simulación sintética (`simulacion.py`), impacto (`impacto.py`) y prevención vial (`prevencion.py`).
- **`backend/`**: API REST en FastAPI (`main.py`), validación Pydantic (`schemas.py`), manejo de errores (`utils.py`) y rutas para conductores (`conductores_api.py`), sesiones y lotes de eventos (`sesiones_api.py`), alertas (`alertas_api.py`) y recorridos (`prevencion_api.py`).
- **`frontend/`**: Interfaz en Streamlit (`app.py`, `estado.py`, `api_client.py`), monitoreo en vivo por WebRTC (`monitoreo_ui.py`), análisis de video grabado (`video_ui.py`), gestión de conductores (`conductor_ui.py`), configuración (`config_ui.py`), historial (`historial_ui.py`), prevención (`prevencion_ui.py`), recorridos (`recorridos_ui.py`) y gráficos Plotly (`graficos.py`).
- **`scripts/`**: Utilidades para descargar modelos (`descargar_modelos.py`), generar recursos base (`generar_recursos.py`) y cargar datos de prueba (`datos_demo.py`). La carpeta `scripts/experimentos/` se creará en las fases experimentales.

### 2. Recorrido de un fotograma (`monitoreo_ui.py` → `alarma.py` → MongoDB)
1. **Captura en hilo de video:** `webrtc_streamer` ejecuta `ProcesadorVideo.recv()` (`frontend/monitoreo_ui.py`, línea 46) en un hilo separado de Streamlit y llama a `ProcesadorConductor.procesar()` (`core/pipeline.py`).
2. **Detección y riesgo:** `DetectorRostro.procesar()` (`core/landmarks.py`) calcula EAR, MAR y ángulos de cabeza; con ellos se construye una `Medicion` que evalúa `MotorRiesgo.actualizar()` (`core/riesgo.py`, línea 145).
3. **Alarma local sin bloquear:** `ProcesadorConductor.procesar()` llama a `Alarma.actualizar()` (`core/alarma.py`, línea 174), que solo actualiza variables bajo `Lock`. El hilo daemon `Alarma._bucle()` (línea 197) consulta ese estado cada 0,1 s y reproduce el sonido mediante `pygame` o `winsound`.
4. **Persistencia en MongoDB:** En el hilo principal de Streamlit, `@st.fragment` (`panel_en_vivo()` y `_enviar_eventos()`) extrae métricas acumuladas y las envía por HTTP (`POST /eventos/lote`) hacia `sesiones_api.eventos_lote()` y `storage.insertar_eventos()` (`core/storage.py`). Nunca se almacenan imágenes ni fotogramas.

### 3. Máquina de estados en `core/riesgo.py`
- **Calibración (`_calibrar`, línea 309):** Al iniciar o pulsar *Recalibrar* (`recalibrar()`), recolecta muestras durante `calibracion_s` (requiere ≥ 5 muestras válidas y mediana de EAR ≥ 0,15) para fijar la línea base personal (`ear_base`, `pitch_base`, `yaw_base`) y el umbral dinámico (`factor_ear * ear_base`).
- **Niveles e histéresis (`actualizar`, línea 145):** Evalúa métricas en ventanas temporales para clasificar en `NORMAL`, `BAJO`, `MEDIO` o `ALTO`. Las subidas de nivel son inmediatas, mientras que las bajadas esperan `histeresis_s` segundos estables para evitar parpadeos de alerta.
- **Sin respuesta y emergencia:** Si el nivel es `ALTO` y persiste ausencia de rostro, ojos cerrados o cabeza caída durante `sin_respuesta_s` (10 s por defecto) sin estar silenciado, activa el cerrojo `emergencia = True`, disparando la cuenta regresiva en `frontend/estado.py`.
- **"Estoy bien" (`reconocer`, línea 131):** Apaga `emergencia`, limpia el historial de evidencia, vuelve a `NORMAL` y activa una ventana de silencio (`silencio_tras_ok_s = 5 s`) conservando la calibración previa.

### 4. Por qué `st.audio` no puede usarse desde el hilo de video
`ProcesadorVideo.recv()` corre en el hilo de procesamiento de `streamlit-webrtc` (`async_processing=True`), fuera del `ScriptRunContext` de Streamlit, por lo que no puede invocar widgets ni modificar la página. Además, al ejecutarse ~30 veces por segundo, llamar a `st.audio` reiniciaría el sonido en cada fotograma. Por ello, `core/alarma.py` desacopla la reproducción en un hilo daemon propio sobre el equipo local.

### 5. Verificación humana y control de alucinaciones
- **Archivos contrastados:** `core/riesgo.py`, `core/alarma.py`, `frontend/monitoreo_ui.py`.
- **Resultado:** Todas las funciones, clases y números de línea citados por OpenCode coincidieron exactamente con el código real. Se detectaron únicamente dos erratas menores de redacción en la respuesta del modelo (`概率 > 0.5` y `reglas earning`), sin impacto en las rutas ni en los nombres de funciones verificados.

### 6. Incidencias y soluciones aplicadas durante la Fase 1
- **Elección de consola agéntica:** Al requerirse suscripción de pago para usar Claude Code, se optó por **OpenCode** con los modelos gratuitos de Zen, manteniendo compatibilidad para ambas herramientas (`AGENTS.md` + `CLAUDE.md` y carpetas `.claude/` + `.opencode/`).
- **Registro de servidores MCP en Windows:** En `claude mcp add` fue necesario colocar `--scope project` antes del nombre del servidor para delimitar las variables de entorno y envolver `npx` con `cmd /c`.
- **Error de módulo en `mongodb-mcp-server`:** Al probar la conexión MCP de MongoDB, `npx` falló con `ERR_MODULE_NOT_FOUND` por una referencia rota a `.esm-wrapper.mjs`. Se solucionó eliminando la caché temporal `_npx`, instalando `mongodb-mcp-server` de forma global con `npm install -g`, corrigiendo la importación a `index.js` en `keychain.js` y apuntando `opencode.jsonc` directamente al ejecutable global.

@'

---

## Fase 2: Verificación del entorno

- **Script implementado:** `scripts/verificar_entorno.py` mediante la skill `@driveguard-verificar-entorno`.
- **Resultado del diagnóstico:** `10 OK | 3 avisos | 0 errores` (Python 3.11.18, `mediapipe 1.2.3`, `cv2 5.1.0`, `fastapi 0.165.0`, `streamlit 1.67.0`, `torch 2.15.0+cpu`, modelo `face_landmark.task` presente, sonidos WAV generados, puerto TCP `27017` de MongoDB abierto y `46 passed` en `pytest`).
- **Avisos revisados:** Uso de `.venv` en lugar de `conda`, omisión intencional de lectura de `.env` por seguridad y API FastAPI aún sin iniciar en el puerto `8000`.