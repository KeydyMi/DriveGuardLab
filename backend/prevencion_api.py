from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.prevencion import Telemetria, evaluar
from core import storage
from datetime import datetime, timezone
from bson import ObjectId

router=APIRouter(tags=["Prevención y recorridos"])

class Lectura(BaseModel):
    velocidad_kmh: float | None = Field(None,ge=0,le=350)
    distancia_m: float | None = Field(None,ge=0,le=10000)
    velocidad_relativa_kmh: float | None = Field(None,ge=-350,le=350)
    lat: float | None = Field(None,ge=-90,le=90)
    lon: float | None = Field(None,ge=-180,le=180)
    conductor_nivel: str = Field("NORMAL",pattern="^(NORMAL|BAJO|MEDIO|ALTO)$")
    fuente_distancia: str = "no_disponible"

class Recorrido(BaseModel):
    conductor_id: str
    origen: str = Field(min_length=2,max_length=250)
    destino: str = Field(min_length=2,max_length=250)

class Punto(BaseModel):
    lat: float = Field(ge=-90,le=90)
    lon: float = Field(ge=-180,le=180)
    velocidad_kmh: float | None = Field(None,ge=0,le=350)

@router.post("/prevencion/evaluar")
def evaluar_lectura(lectura:Lectura):
    return evaluar(Telemetria(**lectura.model_dump()))

@router.post("/recorridos",status_code=201)
def crear_recorrido(datos:Recorrido):
    if storage.obtener_conductor(datos.conductor_id) is None:
        raise HTTPException(404,"Conductor no encontrado")
    doc={**datos.model_dump(),"inicio":datetime.now(timezone.utc),"estado":"activo"}
    return {"id":str(storage.get_db().recorridos.insert_one(doc).inserted_id)}

@router.post("/recorridos/{recorrido_id}/puntos",status_code=201)
def guardar_punto(recorrido_id:str,punto:Punto):
    try: oid=ObjectId(recorrido_id)
    except Exception: raise HTTPException(422,"Identificador inválido")
    db=storage.get_db()
    if not db.recorridos.find_one({"_id":oid,"estado":"activo"}):
        raise HTTPException(404,"Recorrido activo no encontrado")
    db.puntos_recorrido.insert_one({"recorrido_id":recorrido_id,**punto.model_dump(),"fecha":datetime.now(timezone.utc)})
    return {"guardado":True}

@router.put("/recorridos/{recorrido_id}/finalizar")
def finalizar(recorrido_id:str):
    try: oid=ObjectId(recorrido_id)
    except Exception: raise HTTPException(422,"Identificador inválido")
    res=storage.get_db().recorridos.update_one({"_id":oid,"estado":"activo"},{"$set":{"estado":"finalizado","fin":datetime.now(timezone.utc)}})
    if not res.modified_count: raise HTTPException(404,"Recorrido activo no encontrado")
    return {"finalizado":True}

@router.get("/recorridos")
def listar_recorridos(conductor_id:str | None=None):
    q={"conductor_id":conductor_id} if conductor_id else {}
    return [storage._limpiar(x) for x in storage.get_db().recorridos.find(q).sort("inicio",-1).limit(100)]

@router.get("/recorridos/{recorrido_id}/puntos")
def listar_puntos(recorrido_id:str):
    return [storage._limpiar(x) for x in storage.get_db().puntos_recorrido.find({"recorrido_id":recorrido_id}).sort("fecha",1).limit(10000)]
