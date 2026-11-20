# DriveGuard Lab — ampliación de prevención y recorridos

## Funciones añadidas
- API `POST /prevencion/evaluar`: fusiona riesgo de conductor y tiempo hasta colisión (TTC) calculado a partir de **distancia medida** y **velocidad relativa medida**. Sin sensores no se calcula TTC.
- API `POST /recorridos`, `POST /recorridos/{id}/puntos`, `GET /recorridos`, `GET /recorridos/{id}/puntos`, `PUT /recorridos/{id}/finalizar`.
- Pestañas **Prevención** (simulador de sensores) y **Recorridos** (origen, destino, puntos y mapa).
- Notebook 05 y pruebas unitarias.

## Ejecutar desde Anaconda Prompt
```bash
conda create -n driveguard python=3.11 -y
conda activate driveguard
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```
En otra terminal con el mismo entorno:
```bash
streamlit run frontend/app.py
```
MongoDB debe estar ejecutándose y configurado mediante `.env.example` copiado a `.env`. Para el notebook, ejecutar `jupyter lab` desde la raíz del proyecto. Pruebas: `python -m pytest tests/test_prevencion.py -q`.

## Limitaciones de seguridad y próximos pasos de integración
La pestaña Prevención **no mide automáticamente** distancias ni velocidades; admite telemetría manual para simulación. La cámara interior original continúa funcionando en Monitoreo. Para automatizar distancia frontal: integrar cámara frontal calibrada con estimación de profundidad validada, radar o LiDAR; para velocidad, GPS/OBD-II; y para ubicación en vivo, receptor GPS con consentimiento. La velocidad relativa NO es la velocidad del vehículo. TTC supone aproximación constante y no equivale a probabilidad de accidente. No conecta frenos ni dirección y no debe probarse conduciendo en vía pública. No hay geocodificación ni navegación automática: origen y destino son etiquetas introducidas por el usuario. Los datos GPS se guardan solo cuando se pulsa Registrar punto.
