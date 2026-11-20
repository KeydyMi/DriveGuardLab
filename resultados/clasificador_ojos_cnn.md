# Clasificador CNN de ojos vs. umbral EAR

Reproducir: `python scripts/experimentos/clasificador_ojos_cnn.py --semilla 42 --dataset sintetico --epocas 10 --lote 64 --salida resultados --n-muestras 1500`

- Origen de los datos: **SINTÉTICO (demo: no válido como evidencia real)**. Semilla `42`; 300 muestras de prueba sobre las que se comparan ambos métodos.
- Umbral EAR usado: `0.21` = `ConfigRiesgo().ear_umbral_defecto` (solo lectura; **los defaults no se modifican**). Umbral CNN: 0.50 sobre P(cerrado).
- Convención: 0 = cerrado, 1 = abierto. EAR decide *cerrado* si `ear < umbral`; la CNN decide *cerrado* si `P(cerrado) > 0.5`.
- Entrenamiento: 10 épocas, lote 64, Adam lr=1e-3, CPU, semilla fija en numpy/torch. Modelo en memoria: **no se guarda en `models/`**.
- `.env` no se leyó ni editó directamente; `OJOS_METODO` queda como estuviera (en esta ejecución se mantuvo `ear`). No se guardan imágenes de ojos/rostros.

## Métricas comparativas

| Método | Exactitud | Precisión (cerrado) | Sensibilidad (cerrado) | F1 cerrado | F1 macro | ROC AUC | TP | TN | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EAR | 1.000 | 1.000 | 1.000 | **1.000** | 1.000 | 1.000 | 150 | 150 | 0 | 0 |
| CNN | 1.000 | 1.000 | 1.000 | **1.000** | 1.000 | 1.000 | 150 | 150 | 0 | 0 |

Diferencia F1 (CNN − EAR): **+0.000** en la clase cerrado; diferencia ROC AUC: **+0.000**.

## Matrices de confusión

### EAR

| | Pred. cerrado | Pred. abierto |
| --- | --- | --- |
| Real cerrado | 150 | 0 |
| Real abierto | 0 | 150 |

### CNN

| | Pred. cerrado | Pred. abierto |
| --- | --- | --- |
| Real cerrado | 150 | 0 |
| Real abierto | 0 | 150 |

## Conclusión y alcance

- Los dos métodos se miden sobre **las mismas muestras y la misma semilla**; la comparación es pareada.
- Con datos sintéticos limpios ambas reglas pueden separar bien las clases: esto **no es evidencia** de rendimiento con conductores reales, iluminación variable, oclusión o cámaras infrarrojas.
- Para una conclusión válida, repetir con `--dataset local` y EAR medido con MediaPipe en `data/ojos/`, y validar en video etiquetado antes de pensar en activar `OJOS_METODO=cnn`.

## Entrenamiento

| Época | Pérdida media |
| --- | --- |
| 1 | 0.4134 |
| 2 | 0.1927 |
| 3 | 0.1157 |
| 4 | 0.0738 |
| 5 | 0.0452 |
| 6 | 0.0306 |
| 7 | 0.0221 |
| 8 | 0.0182 |
| 9 | 0.0167 |
| 10 | 0.0136 |
