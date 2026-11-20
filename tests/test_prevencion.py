from core.prevencion import Telemetria,evaluar

def test_colision_critica():
    r=evaluar(Telemetria(distancia_m=10,velocidad_relativa_kmh=72))
    assert r["nivel"]=="ALTO" and r["ttc_s"]==0.5

def test_sin_sensor_no_predice():
    r=evaluar(Telemetria(velocidad_kmh=80))
    assert r["ttc_s"] is None and r["nivel"]=="NORMAL"

def test_somnolencia():
    assert evaluar(Telemetria(conductor_nivel="ALTO"))["nivel"]=="ALTO"
