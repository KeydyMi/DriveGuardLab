# Escenarios sintéticos de conducción

Reproducir: `python scripts/experimentos/escenarios_sinteticos.py --semilla 42 --fps 15 --salida resultados`

- Escenarios ejecutados: normal, cansancio, microsueno, sin_respuesta, distraccion, cabeceos, rostro_ausente.
- Semilla: `42`; muestreo: `15` fps; `core.simulacion.generar_mediciones` + `core.simulacion.ejecutar`.
- Umbrales: `ConfigRiesgo()` sin cambios (calibración 10 s, factor EAR 0.75, PERCLOS 30%, microsueño 1.5 s, histeresis 2 s, sin respuesta 10 s).
- Datos por fotograma: `escenarios_sinteticos.csv`. No se guardan imágenes ni se usa cámara.

## Resultados

| Escenario | Nivel máx. | Primer MEDIO | Primer ALTO | Motivos | PERCLOS máx. | Bostezos | Cabeceos | Cierre máx. | Emergencia |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| normal | NORMAL | — | — | — | 11% | 0 | 0 | 0.3 s | No |
| cansancio | MEDIO | 40.0 s | — | bostezos, cansancio_perclos | 45% | 3 | 0 | 0.8 s | No |
| microsueno | ALTO | — | 21.5 s | microsueno | 24% | 0 | 0 | 2.5 s | No |
| sin_respuesta | ALTO | 44.1 s | 21.5 s | cansancio_perclos, microsueno | 70% | 0 | 0 | 22.0 s | 31.5 s |
| distraccion | MEDIO | 23.0 s | — | distraccion | 11% | 0 | 0 | 0.3 s | No |
| cabeceos | MEDIO | 40.5 s | — | cabeceos | 11% | 0 | 3 | 0.3 s | No |
| rostro_ausente | MEDIO | 23.0 s | — | rostro_ausente | 11% | 0 | 0 | 0.3 s | No |

## Hallazgos por escenario

- **normal** (esperado: Conducción estable, sin alertas) — Sin alertas en 60 s; cierre máximo 0.27 s (parpadeos normales). [OK]
- **cansancio** (esperado: MEDIO por PERCLOS alto y bostezos) — PERCLOS máximo 45% (umbral 30 %); 3 bostezos en la ventana de 5 min. [OK]
- **microsueno** (esperado: ALTO por cierre continuo de ojos) — ALTO a los 21.5 s por 2.5 s de ojos cerrados de forma continua. [OK]
- **sin_respuesta** (esperado: ALTO y emergencia tras no responder) — ALTO a los 21.5 s por 22.0 s de ojos cerrados de forma continua; PERCLOS máximo 70% (umbral 30 %); emergencia a los 31.5 s (ALTO sin respuesta durante 10 s). [OK]
- **distraccion** (esperado: MEDIO por giro de cabeza) — Giro de cabeza -> MEDIO a los 23.0 s. [OK]
- **cabeceos** (esperado: MEDIO por cabeceos repetidos) — 3 cabeceos -> MEDIO. [OK]
- **rostro_ausente** (esperado: MEDIO por rostro no visible) — Rostro no visible -> MEDIO a los 23.0 s. [OK]

Nota: el primer MEDIO/ALTO se mide después de la calibración inicial. La emergencia de `sin_respuesta` se cancelaría con «Estoy bien» (`MotorRiesgo.reconocer`), no ejercitado en esta corrida.
