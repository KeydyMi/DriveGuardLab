"""Evaluación de datos externos de cámara frontal/sensores; entrada manual para simulación."""
import streamlit as st
from frontend.api_client import _req, ApiError

def render():
    st.subheader("Prevención de colisiones — simulador y telemetría")
    st.info("La cámara interior analiza al conductor en la pestaña Monitoreo. La distancia y velocidad relativa deben proceder de sensores externos calibrados; aquí se introducen manualmente para demostración.")
    c1,c2=st.columns(2)
    velocidad=c1.number_input("Velocidad del vehículo (km/h)",0.0,350.0,50.0)
    distancia=c2.number_input("Distancia frontal medida (m)",0.0,10000.0,40.0)
    relativa=c1.number_input("Velocidad de aproximación (km/h)",-350.0,350.0,30.0)
    nivel=c2.selectbox("Riesgo del conductor (desde monitor o simulación)",["NORMAL","BAJO","MEDIO","ALTO"])
    lat=st.session_state.ubicacion.get("lat")
    lon=st.session_state.ubicacion.get("lon")
    if st.button("Evaluar riesgo",type="primary"):
        try:
            r=_req("POST","/prevencion/evaluar",json={"velocidad_kmh":velocidad,"distancia_m":distancia,"velocidad_relativa_kmh":relativa,"lat":lat,"lon":lon,"conductor_nivel":nivel,"fuente_distancia":"simulacion_manual"})
            st.metric("Nivel de riesgo",r["nivel"])
            st.metric("Tiempo hasta colisión estimado",f'{r["ttc_s"]} s' if r["ttc_s"] is not None else "No estimable")
            for m in r["motivos"]: st.warning(m)
            if r["nivel"]=="ALTO": st.error("ALERTA: riesgo elevado. Detenerse de forma segura cuando sea posible.")
            st.caption(r["advertencia"])
        except ApiError as exc: st.error(str(exc))
