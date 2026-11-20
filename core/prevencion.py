"""Evaluación conservadora de riesgo vial; no predice accidentes con certeza."""
from dataclasses import dataclass, asdict

@dataclass
class Telemetria:
    velocidad_kmh: float | None = None
    distancia_m: float | None = None
    velocidad_relativa_kmh: float | None = None  # positiva cuando se aproxima al objeto
    lat: float | None = None
    lon: float | None = None
    conductor_nivel: str = "NORMAL"
    fuente_distancia: str = "no_disponible"


def evaluar(t: Telemetria) -> dict:
    motivos=[]
    nivel="NORMAL"
    ttc=None
    if t.distancia_m is not None and t.velocidad_relativa_kmh is not None and t.velocidad_relativa_kmh > 0:
        ttc=t.distancia_m/(t.velocidad_relativa_kmh/3.6)
        if ttc < 1.5:
            nivel="ALTO"; motivos.append("Tiempo hasta colisión estimado inferior a 1,5 s")
        elif ttc < 3:
            nivel="MEDIO"; motivos.append("Tiempo hasta colisión estimado inferior a 3 s")
    if t.conductor_nivel == "ALTO":
        nivel="ALTO"; motivos.append("Conductor con señales de alto riesgo")
    elif t.conductor_nivel == "MEDIO" and nivel == "NORMAL":
        nivel="MEDIO"; motivos.append("Conductor con señales de fatiga o distracción")
    return {"nivel":nivel,"motivos":motivos,"ttc_s":round(ttc,2) if ttc is not None else None,
            "ubicacion":{"lat":t.lat,"lon":t.lon},"datos":asdict(t),
            "advertencia":"Estimación académica; requiere sensores calibrados y validación real"}
