import streamlit as st
import pandas as pd
from frontend.api_client import _req, ApiError

def render():
    st.subheader("Registro de recorridos")
    conductor=st.session_state.get("conductor")
    if not conductor:
        st.info("Seleccione o registre primero un conductor.");return
    origen=st.text_input("Punto de partida",placeholder="Popayán, Cauca")
    destino=st.text_input("Destino",placeholder="Cali, Valle del Cauca")
    if st.button("Iniciar recorrido",disabled=not origen.strip() or not destino.strip()):
        try:
            r=_req("POST","/recorridos",json={"conductor_id":conductor["id"],"origen":origen,"destino":destino})
            st.session_state["recorrido_activo"]=r["id"]
            st.success("Recorrido iniciado")
        except ApiError as exc: st.error(str(exc))
    rid=st.session_state.get("recorrido_activo")
    if rid:
        st.caption(f"Recorrido activo: {rid}")
        c1,c2,c3=st.columns(3)
        lat=c1.number_input("Latitud GPS",-90.0,90.0,3.451600,format="%.6f",key="gps_lat")
        lon=c2.number_input("Longitud GPS",-180.0,180.0,-76.532000,format="%.6f",key="gps_lon")
        vel=c3.number_input("Velocidad GPS km/h",0.0,350.0,0.0)
        st.caption("Ubicación manual de prueba; no se obtiene GPS automáticamente desde Streamlit.")
        if st.button("Registrar punto"):
            try: _req("POST",f"/recorridos/{rid}/puntos",json={"lat":lat,"lon":lon,"velocidad_kmh":vel});st.success("Punto guardado")
            except ApiError as exc: st.error(str(exc))
        if st.button("Finalizar recorrido"):
            try: _req("PUT",f"/recorridos/{rid}/finalizar");st.session_state.pop("recorrido_activo",None);st.success("Recorrido finalizado")
            except ApiError as exc: st.error(str(exc))
    try:
        rows=_req("GET","/recorridos",params={"conductor_id":conductor["id"]})
        if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True)
        if rid:
            puntos=_req("GET",f"/recorridos/{rid}/puntos")
            if puntos: st.map(pd.DataFrame(puntos)[["lat","lon"]])
    except ApiError as exc: st.warning(str(exc))
