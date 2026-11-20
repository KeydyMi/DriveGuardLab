# Informe técnico final — DriveGuardLab

**Fecha:** 20 de noviembre de 2026
**Alcance:** consolidación de las cinco fases verificadas (entorno, escenarios sintéticos, sensibilidad de umbrales, evaluación en video y comparación CNN vs EAR).
**Naturaleza:** prototipo académico de investigación. **No** es un dispositivo médico, ni un sistema de seguridad certificado, ni sustituye la supervisión de un conductor. Los resultados se obtuvieron con datos sintéticos y señales simuladas; consulte el apartado de limitaciones.

---

## 1. Reproducibilidad

Todas las corridas usaron la semilla `42` salvo el diagnóstico de entorno, que es determinista. Los comandos son los declarados por cada script en `resultados/*.md`. No se modificaron los valores por defecto de `ConfigRiesgo`, no se leyó ni editó `.env`, no se usó cámara y no se guardaron imágenes de rostros.

| Fase | Comando | Semilla | Salida principal |
| --- | --- | --- | --- |
| Entorno | `python scripts/verificar_entorno.py` | — (diagnóstico) | `verificacion_entorno.md` |
| Escenarios sintéticos | `python scripts/experimentos/escenarios_sinteticos.py --semilla 42 --fps 15 --salida resultados` | 42 | `escenarios_sinteticos.{csv,md}` |
| Sensibilidad de umbrales | `python scripts/experimentos/sensibilidad_umbrales.py --semilla 42 --fps 15 --salida resultados` | 42 | `sensibilidad_umbrales.{csv,md,png}`, `sensibilidad_umbrales_detalles.csv` |
| Evaluación en video | `python scripts/experimentos/evaluacion_video.py --video data\videos\sintetico_somnolencia.mp4 --semilla 42 --fps 15 --salida resultados` | 42 | `evaluacion_video.{csv,md,png}` (`_resumen`, `_fotogramas`) |
| CNN vs EAR | `python scripts/experimentos/clasificador_ojos_cnn.py --semilla 42 --dataset sintetico --epocas 10 --lote 64 --salida resultados --n-muestras 1500` | 42 | `clasificador_ojos_cnn.{csv,md,png}`, `clasificador_ojos_cnn_predicciones.csv` |

---

## 2. Fase 1 — Verificación del entorno

| Chequeo | Estado | Detalle relevante |
| --- | --- | --- |
| Python | OK | 3.11.18 |
| Entorno | AVISO | `.venv` activo en lugar del entorno conda `DriveGuardLab`; conda no está en `PATH` |
| Dependencias | OK | mediapipe 1.2.3, cv2 5.1.0, fastapi 0.165.0, streamlit 1.67.0, torch 2.15.0+cpu |
| Modelo | OK | `models/face_landmarker.task` (3.8 MB) |
| Sonidos | OK | `alarma_alta.wav` (113 kB), `alarma_media.wav` (60 kB) |
| `.env` | AVISO | Presente; el script no lo lee ni lo imprime |
| MongoDB | OK | Puerto TCP 27017 abierto; el estado real se confirma con `/health` |
| API `/health` | AVISO | No levantada en `127.0.0.1:8000` durante el diagnóstico |
| pytest | OK | 46 pruebas, 1 aviso (ver §8) |

**Conclusión:** el entorno es funcional para los experimentos. Los avisos (virtualenv vs conda, API apagada, `.env` presente) son operativos y no bloquean la reproducción de los resultados.

---

## 3. Fase 2 — Escenarios sintéticos de conducción

Generados con `core.simulacion.generar_mediciones` + `core.simulacion.ejecutar`, 60 s por escenario a 15 fps, ruido con semilla fija y `ConfigRiesgo()` sin cambios (calibración 10 s, factor EAR 0.75, PERCLOS 30 %, microsueño 1.5 s, histéresis 2 s, sin respuesta 10 s).

| Escenario | Nivel máx. | Primer MEDIO | Primer ALTO | Motivos | PERCLOS máx. | Bostezos | Cabeceos | Cierre máx. | Emergencia |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| normal | NORMAL | — | — | — | 11 % | 0 | 0 | 0.3 s | No |
| cansancio | MEDIO | 40.0 s | — | bostezos, cansancio_perclos | 45 % | 3 | 0 | 0.8 s | No |
| microsueno | ALTO | — | 21.5 s | microsueno | 24 % | 0 | 0 | 2.5 s | No |
| sin_respuesta | ALTO | 44.1 s | 21.5 s | cansancio_perclos, microsueno | 70 % | 0 | 0 | 22.0 s | 31.5 s |
| distraccion | MEDIO | 23.0 s | — | distraccion | 11 % | 0 | 0 | 0.3 s | No |
| cabeceos | MEDIO | 40.5 s | — | cabeceos | 11 % | 0 | 3 | 0.3 s | No |
| rostro_ausente | MEDIO | 23.0 s | — | rostro_ausente | 11 % | 0 | 0 | 0.3 s | No |

**Hallazgo:** los siete escenarios produjeron el nivel y el motivo esperados. El caso `sin_respuesta` escaló a ALTO a los 21.5 s y disparó emergencia a los 31.5 s (ALTO sostenido 10 s). La cancelación mediante «Estoy bien» (`MotorRiesgo.reconocer`) no se ejerció en esta corrida. Los tiempos se miden después de la calibración inicial.

---

## 4. Fase 3 — Sensibilidad de umbrales

Barrido con `ConfigRiesgo.desde_dict(...)` sobre las mismas mediciones con ruido de semilla fija: las diferencias entre filas se deben solo al parámetro barrido. *Detecciones* = casos con nivel/motivo (y emergencia cuando aplica) esperados tras el evento. *Falsas alarmas* = segundos con nivel ≠ NORMAL en `normal`, más alertas anticipadas/tardías (columnas separadas). Los valores por defecto no se cambiaron.

| Parámetro | Rango barrido | Pérdida de detección | Falsas alarmas | Default = recomendado |
| --- | --- | --- | --- | --- |
| `factor_ear` (EAR) | 0.20 – 0.95 | ≤ 0.30 (0/2) | 0 s en todo el rango | **0.75** |
| `perclos_umbral` (PERCLOS) | 2 % – 50 % | 50 % (0/1) | 20 s con 2 % y 5 % | **30 %** |
| `microsueno_s` (TIEMPOS) | 0.5 – 3 s | 3 s (1/2) | 0 s en todo el rango | **1.5 s** |
| `sin_respuesta_s` (TIEMPOS) | 3 – 30 s | ≥ 25 s (0/1) | 0 s en todo el rango | **10 s** |
| `histeresis_s` (TIEMPOS) | 0 – 10 s | Ninguna (2/2 siempre) | 0 s; solo retrasa el retorno a NORMAL (0.05 → 10.05 s) | **2 s** |

**Hallazgo:** en todos los barridos el valor por defecto coincide con el recomendado: detecta todos los casos esperados con cero falsas alarmas. Los ajustes críticos son los que cruzan la ventana del evento: un EAR demasiado bajo deja de reconocer ojos cerrados, un PERCLOS demasiado alto pierde el cansancio y un `microsueno_s` mayor que el cierre sintético (2.5 s) elimina la alerta ALTO. `sin_respuesta_s` solo desplaza el momento de la emergencia y `histeresis_s` afecta al retorno, no a la subida de nivel.

---

## 5. Fase 4 — Evaluación del pipeline sobre video grabado

Video sintético `data\videos\sintetico_somnolencia.mp4` (50 s, 15 fps, 750 fotogramas): parpadeos normales y calibración (0–11 s), conducción estable, cierre de ojos 3 s (16–19 s), tres bostezos (24–39.5 s), rostro fuera de cámara 6 s (41–47 s) y recuperación final. Sin cámara ni `streamlit-webrtc`; no se guardaron fotogramas.

| Métrica | Valor |
| --- | --- |
| FPS de flujo (frames / tiempo total) | 48.88 |
| FPS de procesamiento (1 / latencia media) | 53.73 |
| Latencia media / p50 / p95 / máx | 18.6 / 19.1 / 26.2 / 59.4 ms |
| Latencia media de MediaPipe | 17.5 ms |
| Fotogramas con rostro | 660 / 750 |
| Nivel máximo global | **ALTO** |
| Tiempos tras calibración (NORMAL / BAJO / MEDIO / ALTO) | 24.4 / 0.0 / 12.0 / 3.6 s |

| Motivo | Primera aparición | Fotogramas | Nivel máx. |
| --- | --- | --- | --- |
| microsueno | 17.53 s | 54 | ALTO |
| bostezos | 38.00 s | 180 | MEDIO |
| rostro_ausente | 44.00 s | 45 | MEDIO |

Eventos: 3 cambios de nivel (ALTO/microsueno a 17.53 s, NORMAL a 21.13 s, MEDIO/bostezos a 38.00 s) y 20 muestras periódicas; 0 fotogramas en emergencia.

**Hallazgo:** el motor de riesgo original reaccionó al guion previsto y la latencia medida (≈18.6 ms, p95 ≈26.2 ms) es compatible con procesamiento en tiempo real en este equipo. **Matiz importante:** MediaPipe se ejecutó en cada fotograma para medir latencia real, pero EAR/MAR se sustituyeron por una señal determinista de semilla fija porque las ediciones del retrato de muestra no cambian los landmarks. Por tanto, las detecciones validan el flujo del motor y la latencia, **no** la precisión perceptiva del pipeline ante imágenes reales.

---

## 6. Fase 5 — Comparación CNN vs EAR

Comparación pareada sobre 300 muestras de prueba sintéticas (1500 generadas, semilla 42). Convención: 0 = cerrado, 1 = abierto; EAR decide cerrado si `ear < 0.21` (`ear_umbral_defecto`, solo lectura) y la CNN si `P(cerrado) > 0.5`. Entrenamiento: 10 épocas, lote 64, Adam lr=1e-3, CPU, semilla fija en numpy/torch, modelo en memoria (no guardado en `models/`).

| Método | Exactitud | Precisión (cerrado) | Sensibilidad (cerrado) | F1 cerrado | F1 macro | ROC AUC | TP / TN / FP / FN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EAR | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 150 / 150 / 0 / 0 |
| CNN | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 150 / 150 / 0 / 0 |

Diferencia F1 (CNN − EAR): **+0.000**; diferencia ROC AUC: **+0.000**. Pérdida de entrenamiento: 0.4134 (época 1) → 0.0136 (época 10).

**Hallazgo:** con datos limpios y separables, la regla de EAR simple empata a la CNN en todas las métricas. El resultado no justifica activar `OJOS_METODO=cnn`: no hay ganancia medible y la CNN añade coste de entrenamiento e inferencia. `OJOS_METODO` quedó sin cambios (`ear`).

---

## 7. Síntesis de hallazgos

1. **El motor de riesgo se comporta según lo diseñado** en los siete escenarios sintéticos y en el video guionado: niveles, motivos y emergencia aparecen en los momentos previstos.
2. **La calibración actual es robusta dentro del espacio barrido**: los cinco defaults (EAR 0.75, PERCLOS 30 %, microsueño 1.5 s, sin respuesta 10 s, histéresis 2 s) son simultáneamente los que detectan todo sin falsas alarmas. No hay motivo para modificar `ConfigRiesgo`.
3. **La sensibilidad se concentra en tres parámetros**: EAR bajo (pérdida de cierre), PERCLOS alto (pérdida de cansancio) y microsueño por encima de la duración del evento. `sin_respuesta_s` e `histeresis_s` desplazan tiempos, no cambian la detección.
4. **El rendimiento en tiempo real es viable en el equipo de prueba**: ≈54 fps de procesamiento, p95 de latencia ≈26 ms, con MediaPipe ejecutándose efectivamente.
5. **La CNN no aporta ventaja sobre EAR** en las condiciones evaluadas: empate exacto en métricas con datos sintéticos limpios.

---

## 8. Limitaciones

- **Datos sintéticos:** los cinco experimentos usan señales simuladas o conjuntos generados con semilla fija. No hay evidencia con conductores reales, iluminación variable, oclusión, gafas, maquillaje ni cámaras infrarrojas.
- **Video no representativo:** el video usa un retrato de muestra como fondo y EAR/MAR deterministas; mide latencia y lógica de alertas, no exactitud perceptiva. Un solo video no permite calcular sensibilidad ni tasa de falsas alarmas (esas métricas provienen de los escenarios de verdad conocida).
- **Comparación CNN vs EAR no concluyente:** ambas clasificaciones son perfectas porque las muestras son limpias y separables. El empate (ΔF1 = 0) no demuestra equivalencia en condiciones reales; antes de activar la CNN haría falta repetir con `--dataset local`, EAR medido con MediaPipe sobre `data/ojos/` y validación en video etiquetado.
- **Recomendaciones condicionadas:** los umbrales recomendados se derivan de los escenarios sintéticos y no sustituyen una validación clínica/operativa con personas.
- **Entorno:** se usó `.venv` en lugar del entorno conda `DriveGuardLab` documentado; la API no estaba levantada durante el diagnóstico (el estado real de MongoDB se confirma con `/health`).
- **Pruebas:** `python -m pytest` → **46 passed, 1 warning** (StarletteDeprecationWarning de `fastapi/testclient.py` por el uso de `httpx`, ajeno a la lógica del proyecto).
- **Alcance del prototipo:** sistema académico experimental; las alertas, la emergencia y los sonidos no deben interpretarse como una garantía de seguridad y requieren supervisor humano.

---

## 9. Verificación final y cierre

- `git status --short`: sin cambios pendientes antes de este informe; no hay notebooks nuevos ni imágenes/videos de rostros versionados. `resultados/` contiene solo CSV, PNG y MD.
- `python -m pytest`: 46 pruebas superadas, 1 aviso de dependencia (detalle en §8).
- Se propone un commit pequeño con Conventional Commit en español, por ejemplo: `docs(resultados): consolidar informe técnico final de las cinco fases`. **No se realiza `git push` ni se borran ramas.**

### Inventario de artefactos

```
resultados/
  verificacion_entorno.md
  escenarios_sinteticos.csv / .md
  sensibilidad_umbrales.csv / .md / .png / _detalles.csv
  evaluacion_video.csv / .md / .png / _resumen.csv / _fotogramas.csv
  clasificador_ojos_cnn.csv / .md / .png / _predicciones.csv
  informe_tecnico_final.md   <- este documento
```
