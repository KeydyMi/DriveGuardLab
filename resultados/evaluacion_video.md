# Evaluación del pipeline sobre video grabado

Reproducir: `python scripts/experimentos/evaluacion_video.py --video data\videos\sintetico_somnolencia.mp4 --semilla 42 --fps 15 --salida resultados`

- Video: `data\videos\sintetico_somnolencia.mp4` (sintético); semilla `42`; `15` fps del video.
- Sin cámara, sin `streamlit-webrtc` y sin guardar fotogramas: solo CSV/PNG/MD en `resultados/`. No se lee `.env`.
- `ConfigRiesgo()` sin cambios (calibración 10 s, factor EAR 0.75, microsueño 1.5 s, MAR 0.6, 3 bostezos/5 min, histéresis 2 s).
- Retrato de muestra `matplotlib:grace_hopper.jpg` usado solo como fondo. MediaPipe se ejecuta en cada fotograma para medir latencia real; EAR/MAR se sustituyen por una señal determinista (semilla fija) porque las ediciones del retrato no cambian los landmarks del modelo. Motor de riesgo y eventos: código original del proyecto.

## Guion del video sintético

| Fase | Intervalo (s) | Descripción |
| --- | --- | --- |
| 0–11 | 11 | Parpadeos normales; calibración de 10 s |
| 11–16 | 5 | Conducción estable |
| 16–19 | 3 | Ojos cerrados 3 s |
| 19–24 | 5 | Recuperación |
| 24–27.5 | 3.5 | Bostezo 1 |
| 27.5–30 | 2.5 | Recuperación |
| 30–33.5 | 3.5 | Bostezo 2 |
| 33.5–36 | 2.5 | Recuperación |
| 36–39.5 | 3.5 | Bostezo 3 |
| 39.5–41 | 1.5 | Recuperación |
| 41–47 | 6 | Rostro fuera de cámara 6 s |
| 47–50 | 3 | Recuperación final |

## Rendimiento

| Métrica | Valor |
| --- | --- |
| Fotogramas procesados | 750 |
| Duración del video | 50.00 s |
| Tiempo total (lectura + procesamiento) | 15.34 s |
| FPS de flujo (frames / tiempo total) | 48.88 |
| FPS de procesamiento (1 / latencia media) | 53.73 |
| Latencia media / p50 / p95 / máx | 18.6 / 19.1 / 26.2 / 59.4 ms |
| Latencia media de MediaPipe | 17.5 ms |
| Fotogramas con rostro | 660 / 750 |

La latencia es tiempo de reloj de pared: depende del equipo. El FPS del pipeline calculado con `t` del video sería el `fps_video`; aquí se reporta el rendimiento real.

## Detecciones

| Motivo | Primera aparición | Fotogramas | Nivel máx. |
| --- | --- | --- | --- |
| microsueno | 17.53 s | 54 | ALTO |
| bostezos | 38.00 s | 180 | MEDIO |
| rostro_ausente | 44.00 s | 45 | MEDIO |

Nivel máximo global: **ALTO**. Tiempos tras la calibración: NORMAL 24.4 s, BAJO 0.0 s, MEDIO 12.0 s, ALTO 3.6 s.
Eventos: 3 cambios de nivel y 20 muestras periódicas; fotogramas en emergencia: 0.

### Eventos de cambio de nivel

| t (s) | Nivel | Anterior | Motivo |
| --- | --- | --- | --- |
| 17.53 | ALTO | NORMAL | microsueno |
| 21.13 | NORMAL | ALTO | — |
| 38.00 | MEDIO | NORMAL | bostezos |

Nota: con un solo video no se calculan sensibilidad ni falsas alarmas; esas métricas se cubren en `sensibilidad_umbrales.md` con escenarios de verdad conocida.
