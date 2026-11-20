# Sensibilidad de umbrales: EAR, PERCLOS y tiempos de respuesta

Reproducir: `python scripts/experimentos/sensibilidad_umbrales.py --semilla 42 --fps 15 --salida resultados`

- Semilla `42`; `15` fps; escenarios: cansancio, distraccion, microsueno, normal, sin_respuesta.
- Los umbrales se aplican con `ConfigRiesgo.desde_dict(...)`; **los valores por defecto de `ConfigRiesgo` no se modifican** y no se lee/escribe `.env`.
- Cada valor se evalúa sobre las mismas mediciones (ruido con semilla fija): las diferencias entre filas se deben solo al umbral barrido.
- **Detecciones**: casos con el nivel/motivo (y emergencia cuando aplica) esperados después del inicio del evento. **Falsas alarmas**: segundos con nivel != NORMAL en `normal` más las alertas fuera de la ventana del evento (anticipadas/tardías, columnas separadas).
- Referencia: calibración 10 s, factor EAR 0.75, PERCLOS 30%, microsueño 1.5 s, sin respuesta 10 s, histéresis 2 s.

## EAR: `factor_ear`

Parámetro de la pestaña *Configuración*: **Factor del EAR base**. Casos evaluados: microsueno, sin_respuesta.

| Valor | Detecciones | Falsas alarmas (normal) | Alertas anticipadas | Alertas tardías | Detección | Default | Recomendado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.2 | 0/2 | 0.00 s | 0.00 s | 0.00 s | — | no | no |
| 0.25 | 0/2 | 0.00 s | 0.00 s | 0.00 s | — | no | no |
| 0.3 | 0/2 | 0.00 s | 0.00 s | 8.00 s | — | no | no |
| 0.35 | 2/2 | 0.00 s | 0.00 s | 10.00 s | 1.67 s | no | no |
| 0.5 | 2/2 | 0.00 s | 0.00 s | 10.00 s | 1.67 s | no | no |
| 0.75 | 2/2 | 0.00 s | 0.00 s | 10.07 s | 1.53 s | sí | sí |
| 0.95 | 2/2 | 0.00 s | 0.00 s | 10.13 s | 1.53 s | no | no |

**Recomendado: 0.75** — El valor por defecto ya detecta todos los casos sin falsas alarmas; se conserva.

Impacto: Pierden detecciones con 0.2, 0.25, 0.3; las alertas tardías van de 0 s a 10.13 s; el default da 2/2 con 0 s de falsas alarmas y 1.53 s de detección; la recomendación (0.75) da 2/2 y 1.53 s.

## PERCLOS: `perclos_umbral`

Parámetro de la pestaña *Configuración*: **Umbral de PERCLOS**. Casos evaluados: cansancio.

| Valor | Detecciones | Falsas alarmas (normal) | Alertas anticipadas | Alertas tardías | Detección | Default | Recomendado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 % | 1/1 | 20.00 s | 0.00 s | 0.00 s | 25.00 s | no | no |
| 5 % | 1/1 | 20.00 s | 0.00 s | 0.00 s | 25.00 s | no | no |
| 10 % | 1/1 | 0.00 s | 0.00 s | 0.00 s | 25.00 s | no | no |
| 20 % | 1/1 | 0.00 s | 0.00 s | 0.00 s | 25.00 s | no | no |
| 30 % | 1/1 | 0.00 s | 0.00 s | 0.00 s | 25.00 s | sí | sí |
| 35 % | 1/1 | 0.00 s | 0.00 s | 0.00 s | 25.00 s | no | no |
| 40 % | 1/1 | 0.00 s | 0.00 s | 0.00 s | 26.73 s | no | no |
| 50 % | 0/1 | 0.00 s | 0.00 s | 0.00 s | — | no | no |

**Recomendado: 30 %** — El valor por defecto ya detecta todos los casos sin falsas alarmas; se conserva.

Impacto: Pierden detecciones con 50 %; falsas alarmas en `normal` con 2 % (20 s), 5 % (20 s); el default da 1/1 con 0 s de falsas alarmas y 25.00 s de detección; la recomendación (30 %) da 1/1 y 25.00 s.

## TIEMPOS: `microsueno_s`

Parámetro de la pestaña *Configuración*: **Microsueño: cierre continuo (s)**. Casos evaluados: microsueno, sin_respuesta.

| Valor | Detecciones | Falsas alarmas (normal) | Alertas anticipadas | Alertas tardías | Detección | Default | Recomendado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5 s | 2/2 | 0.00 s | 0.00 s | 10.07 s | 0.53 s | no | no |
| 1 s | 2/2 | 0.00 s | 0.00 s | 10.07 s | 1.00 s | no | no |
| 1.5 s | 2/2 | 0.00 s | 0.00 s | 10.07 s | 1.53 s | sí | sí |
| 2 s | 2/2 | 0.00 s | 0.00 s | 10.07 s | 2.00 s | no | no |
| 2.5 s | 2/2 | 0.00 s | 0.00 s | 10.07 s | 2.53 s | no | no |
| 3 s | 1/2 | 0.00 s | 0.00 s | 8.00 s | 3.00 s | no | no |

**Recomendado: 1.5 s** — El valor por defecto ya detecta todos los casos sin falsas alarmas; se conserva.

Impacto: Pierden detecciones con 3 s; las alertas tardías van de 8 s a 10.07 s; el default da 2/2 con 0 s de falsas alarmas y 1.53 s de detección; la recomendación (1.5 s) da 2/2 y 1.53 s.

## TIEMPOS: `sin_respuesta_s`

Parámetro de la pestaña *Configuración*: **Sin respuesta → emergencia (s)**. Casos evaluados: sin_respuesta.

| Valor | Detecciones | Falsas alarmas (normal) | Alertas anticipadas | Alertas tardías | Detección | Default | Recomendado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3 s | 1/1 | 0.00 s | 0.00 s | 0.00 s | 4.53 s | no | no |
| 5 s | 1/1 | 0.00 s | 0.00 s | 0.00 s | 6.53 s | no | no |
| 10 s | 1/1 | 0.00 s | 0.00 s | 0.00 s | 11.53 s | sí | sí |
| 15 s | 1/1 | 0.00 s | 0.00 s | 0.00 s | 16.60 s | no | no |
| 20 s | 1/1 | 0.00 s | 0.00 s | 0.00 s | 21.60 s | no | no |
| 25 s | 0/1 | 0.00 s | 0.00 s | 0.00 s | — | no | no |
| 30 s | 0/1 | 0.00 s | 0.00 s | 0.00 s | — | no | no |

**Recomendado: 10 s** — El valor por defecto ya detecta todos los casos sin falsas alarmas; se conserva.

Impacto: Pierden detecciones con 25 s, 30 s; el default da 1/1 con 0 s de falsas alarmas y 11.53 s de detección; la recomendación (10 s) da 1/1 y 11.53 s.

## TIEMPOS: `histeresis_s`

Parámetro de la pestaña *Configuración*: **Histéresis al bajar de nivel (s)**. Casos evaluados: microsueno, distraccion.

| Valor | Detecciones | Falsas alarmas (normal) | Alertas anticipadas | Alertas tardías | Retorno a normal | Default | Recomendado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 s | 2/2 | 0.00 s | 0.00 s | 0.07 s | 0.05 s | no | no |
| 0.5 s | 2/2 | 0.00 s | 0.00 s | 1.13 s | 0.58 s | no | no |
| 1 s | 2/2 | 0.00 s | 0.00 s | 2.07 s | 1.05 s | no | no |
| 2 s | 2/2 | 0.00 s | 0.00 s | 4.07 s | 2.05 s | sí | sí |
| 4 s | 2/2 | 0.00 s | 0.00 s | 8.07 s | 4.05 s | no | no |
| 6 s | 2/2 | 0.00 s | 0.00 s | 12.07 s | 6.05 s | no | no |
| 10 s | 2/2 | 0.00 s | 0.00 s | 20.07 s | 10.05 s | no | no |

**Recomendado: 2 s** — El valor por defecto ya detecta todos los casos sin falsas alarmas; se conserva.

Impacto: Las alertas tardías van de 0.07 s a 20.07 s; el default da 2/2 con 0 s de falsas alarmas y 2.05 s de retorno; la recomendación (2 s) da 2/2 y 2.05 s.

## Conclusión

Los ajustes más sensibles son los que cruzan la ventana del evento: un EAR demasiado bajo deja de reconocer ojos cerrados, un PERCLOS demasiado alto pierde el cansancio y un `microsueno_s` mayor que el cierre sintético (2,5 s) elimina la alerta ALTO. `sin_respuesta_s` solo desplaza el momento de la emergencia, y `histeresis_s` no retrasa la subida de nivel pero sí el retorno a NORMAL.

La recomendación se calcula sobre estos escenarios sintéticos; no sustituye una validación con conductores reales y **no cambia los defaults** de la aplicación.
