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

## Fase 2: Verificación del entorno

- **Script implementado:** `scripts/verificar_entorno.py` mediante la skill `@driveguard-verificar-entorno`.
- **Resultado del diagnóstico:** `10 OK | 3 avisos | 0 errores` (Python 3.11.18, `mediapipe 1.2.3`, `cv2 5.1.0`, `fastapi 0.165.0`, `streamlit 1.67.0`, `torch 2.15.0+cpu`, modelo `face_landmark.task` presente, sonidos WAV generados, puerto TCP `27017` de MongoDB abierto y `46 passed` en `pytest`).
- **Avisos revisados:** Uso de `.venv` en lugar de `conda`, omisión intencional de lectura de `.env` por seguridad y API FastAPI aún sin iniciar en el puerto `8000`.

## Fase 3: Experimentos con escenarios sintéticos (`@driveguard-escenarios`)

- **Script implementado:** `scripts/experimentos/escenarios_sinteticos.py` (ejecutado con `--semilla 42` y `--fps 15`, reutilizando `core.simulacion` y `core.riesgo` sin alterar `ConfigRiesgo`).
- **Artefactos generados:** `resultados/escenarios_sinteticos.csv` (5.850 registros por fotograma) y `resultados/escenarios_sinteticos.md`.
- **Resultados verificados (`[OK]` en los 7 escenarios):**
  - `normal`: se mantiene en `NORMAL` durante los 60 s (cierre máximo 0,27 s, PERCLOS 11 %), sin alertas.
  - `cansancio`: escala a `MEDIO` a los 40,0 s (PERCLOS máximo 45 %, 3 bostezos).
  - `microsueno`: escala a `ALTO` a los 21,5 s por 2,5 s de ojos cerrados continuos, sin emergencia.
  - `sin_respuesta`: escala a `ALTO` a los 21,5 s (22,0 s de cierre continuo, PERCLOS 70 %) y dispara `emergencia` a los 31,5 s tras 10 s sin respuesta.
  - `distraccion`, `cabeceos` y `rostro_ausente`: escalan a `MEDIO` en 23,0 s, 40,5 s (3 cabeceos) y 23,0 s respectivamente.
- **Validación:** Determinismo comprobado mediante hashes idénticos entre corridas consecutivas y `46 passed` en `pytest`.

## Fase 4: Análisis de sensibilidad de umbrales (`@driveguard-umbrales`)

- **Script implementado:** `scripts/experimentos/sensibilidad_umbrales.py` (ejecutado con `--semilla 42 --fps 15`, aplicando variaciones mediante `ConfigRiesgo.desde_dict()` sin alterar los valores por defecto).
- **Artefactos generados:** `resultados/sensibilidad_umbrales.csv` (35 combinaciones), `resultados/sensibilidad_umbrales_detalles.csv`, `resultados/sensibilidad_umbrales.md` y `resultados/sensibilidad_umbrales.png` (5 paneles).
- **Hallazgos por parámetro:**
  - `factor_ear`: `0.20–0.30` pierden detecciones (`0/2`); el default `0.75` detecta `2/2` en `1.53 s` con `0 s` de falsas alarmas.
  - `perclos_umbral`: `2–5 %` producen `20 s` de falsas alarmas en `normal` y `50 %` pierde `cansancio` (`0/1`); el default `30 %` logra `1/1` sin falsas alarmas.
  - `microsueno_s`: `3.0 s` supera el cierre sintético de `2.5 s` (`1/2`); el default `1.5 s` detecta `2/2`.
  - `sin_respuesta_s`: `25–30 s` no llegan a disparar emergencia (`0/1`); el default `10 s` la activa de forma consistente.
  - `histeresis_s`: mantiene `2/2` detecciones en todos los valores, pero al subir de `0 s` a `10 s` el retorno a `NORMAL` aumenta de `0.05 s` a `10.05 s`; el default `2 s` equilibra estabilidad y tiempo de recuperación.
- **Verificación visual humana (`sensibilidad_umbrales.png`):** Gráfica legible sin etiquetas solapadas; los 5 valores por defecto se ubican en la zona de 100 % detecciones y 0 s de falsas alarmas. Se observó únicamente que la leyenda muestra `Default` en gris punteado mientras la línea vertical es verde discontinua, y que el eje X de PERCLOS expresa el porcentaje como proporción (`0.0–0.5`).
- **Decisión y validación:** Se conservan los cinco valores por defecto de `ConfigRiesgo`. Suite `pytest` en verde (`46 passed`).

## Fase 5: Evaluación sobre video (`@driveguard-video`)

- **Script implementado:** `scripts/experimentos/evaluacion_video.py` (ejecutado sobre un clip sintético de 50,0 s / 750 fotogramas a 15 fps guardado localmente en `data/videos/` e ignorado por Git).
- **Enfoque técnico:** MediaPipe `FaceLandmarker` procesó los 750 fotogramas reales para medir latencia de inferencia, mientras que EAR/MAR se inyectaron con semilla fija para reproducir eventos controlados sin alterar `core/riesgo.py` ni `ConfigRiesgo`.
- **Artefactos generados:** `resultados/evaluacion_video_fotogramas.csv`, `resultados/evaluacion_video_resumen.csv`, `resultados/evaluacion_video.md` y `resultados/evaluacion_video.png`.
- **Rendimiento medido:**
  - Tiempo total: `15,34 s` | FPS de flujo: `48,9 FPS` | FPS de procesamiento: `53,7 FPS`.
  - Latencia total: media `18,6 ms`, p50 `19,1 ms`, p95 `26,2 ms`, máxima `59,4 ms` (latencia media de MediaPipe: `17,5 ms`).
- **Detecciones registradas:** `microsueno` a los `17,53 s` (`ALTO`, 3,6 s), `bostezos` a los `38,00 s` (`MEDIO`, 12,0 s) y `rostro_ausente` a los `44,00 s` (`MEDIO`, 3,0 s). Nivel máximo `ALTO`, sin emergencia.
- **Verificación visual humana (`evaluacion_video.png`):** Gráfica libre de rostros; muestra con claridad el ajuste del umbral EAR tras la calibración de 10 s, la transición a `ALTO` en el microsueño, los 3 picos de MAR y el estado `MEDIO` durante bostezos y ausencia de rostro, además de la distribución de latencia (`p50 = 19,1 ms`, `p95 = 26,2 ms`). Se observó que los tres paneles comparten el eje X (`0–60`) combinando segundos arriba y milisegundos en el histograma inferior.
- **Validación:** Verificado con `git check-ignore` que ningún `.mp4` entra al repositorio; `pytest` en verde (`46 passed`).

## Fase 6: Clasificador CNN de ojos frente a EAR (`@driveguard-cnn`)

- **Autorización y control de entorno:** Ante la ausencia de imágenes reales en `data/ojos/` y de pesos preentrenados en `models/cnn_ojos.pt`, se autorizó explícitamente la ejecución en modo demostración sintética (`SYNTHETIC`) manteniendo `OJOS_METODO=ear` y sin modificar `.env` ni `ConfigRiesgo`.
- **Script implementado:** `scripts/experimentos/clasificador_ojos_cnn.py` (con soporte `--semilla`, `--dataset`, `--salida` y compatibilidad futura para `--dataset local --ear-csv ...`). Genera los recortes en memoria, entrena `crear_cnn()` de `core/ojos_cnn.py` durante 10 épocas y compara contra el umbral EAR (`0.21`).
- **Artefactos generados:** `resultados/clasificador_ojos_cnn.csv`, `resultados/clasificador_ojos_cnn_predicciones.csv`, `resultados/clasificador_ojos_cnn.md` y `resultados/clasificador_ojos_cnn.png` (sin guardar imágenes de ojos/rostros ni pesos en `models/`).
- **Resultados comparativos (`SYNTHETIC`, 300 muestras de prueba, semilla 42):**
  - **EAR (`umbral = 0.21`):** F1 cerrado `1.000`, F1 macro `1.000`, ROC AUC `1.000` (`TP=150, TN=150, FP=0, FN=0`).
  - **CNN (`P(cerrado) > 0.5`):** F1 cerrado `1.000`, F1 macro `1.000`, ROC AUC `1.000` (`TP=150, TN=150, FP=0, FN=0`), con pérdida de entrenamiento descendente de `0.413` a `0.014`.
- **Verificación visual humana (`clasificador_ojos_cnn.png`):** Cuatro paneles legibles (`2700 x 630`) con encabezado explícito de demostración sintética; matrices de confusión diagonales (`150/150` en ambos métodos), curvas ROC superpuestas en `AUC=1.000` y descenso continuo de la pérdida a lo largo de las 10 épocas.
- **Interpretación metodológica:** En datos sintéticos limpios ambos métodos separan perfectamente las clases (`diferencia +0.000`), lo que valida el flujo de entrenamiento y comparación pero **no constituye evidencia de desempeño real** bajo variaciones de iluminación, oclusión o cámara infrarroja; se conserva `ear` como método activo hasta evaluar con un dataset real etiquetado.
- **Validación:** Hashes SHA256 idénticos entre corridas consecutivas y `46 passed` en `pytest`.

## Fase 7: Consolidación del informe técnico final (`@driveguard-informe`)

- **Artefacto generado:** `resultados/informe_tecnico_final.md`, integrando la matriz de reproducibilidad (semilla `42`), métricas, tablas y enlaces a los artefactos de todas las fases previas.
- **Síntesis de resultados del laboratorio:**
  - **Entorno y pruebas:** Diagnóstico sin errores bloqueantes y `46 passed` en `pytest` a lo largo de todas las fases.
  - **Motor de riesgo (`core/riesgo.py`):** Los 7 escenarios sintéticos y la prueba sobre video dispararon los niveles `NORMAL`, `MEDIO`, `ALTO` y `emergencia` en los tiempos esperados.
  - **Calibración de umbrales:** El barrido de sensibilidad confirmó que los 5 valores por defecto de `ConfigRiesgo` (`factor_ear=0.75`, `perclos_umbral=30%`, `microsueno_s=1.5s`, `sin_respuesta_s=10s`, `histeresis_s=2s`) logran 100 % de detección con 0 s de falsas alarmas.
  - **Desempeño en tiempo real:** El pipeline alcanzó `~53,7 FPS` de procesamiento (`48,9 FPS` de flujo) con latencia media de `18,6 ms` (`p95 = 26,2 ms`), ejecutando MediaPipe `FaceLandmarker` real sobre los 750 fotogramas.
  - **Clasificador CNN vs. EAR:** En la demostración sintética (`SYNTHETIC`), ambos métodos obtuvieron `F1 = 1.000` y `ROC AUC = 1.000` (`Δ = 0.000`), por lo que se mantiene `OJOS_METODO=ear` hasta validar con un dataset real etiquetado.
- **Limitaciones documentadas:** Evaluación basada en escenarios sintéticos y video controlado (sin variaciones reales de iluminación, oclusión ni cámaras IR), lo que delimita el sistema como prototipo académico reproducible.