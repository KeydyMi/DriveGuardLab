"""Verificación completa del entorno de DriveGuard Lab.

Uso (desde la raíz del repo):
    python scripts/verificar_entorno.py
    python scripts/verificar_entorno.py --sin-pytest
    python scripts/verificar_entorno.py --informe

Comprueba Python 3.11, el entorno activo, los imports clave, el modelo y los
sonidos, los servicios (MongoDB en localhost:27017 y /health de la API) y la
suite pytest. No instala nada, no lee .env y no crea notebooks. Sin
aleatoriedad: no requiere semilla fija.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONGO_HOST = "127.0.0.1"
MONGO_PORT = 27017
API_HEALTH = "http://127.0.0.1:8000/health"
IMPORTES_CLAVE = ("mediapipe", "cv2", "fastapi", "streamlit", "torch")
MODELO = ROOT / "models" / "face_landmarker.task"
INFORME = ROOT / "resultados" / "verificacion_entorno.md"


@dataclass
class Chequeo:
    nombre: str
    estado: str
    detalle: str

    def linea(self) -> str:
        return f"[{self.estado:<5}] {self.nombre}: {self.detalle}"


def cortar(texto: object, limite: int = 160) -> str:
    """Acorta un mensaje para que el resumen siga siendo legible."""
    limpio = " ".join(str(texto).split())
    return limpio if len(limpio) <= limite else limpio[: limite - 3] + "..."


def revisar_python() -> Chequeo:
    version = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info[:2] == (3, 11):
        return Chequeo("Python", "OK", f"{version} ({Path(sys.executable).name})")
    return Chequeo(
        "Python",
        "ERROR",
        f"Se requiere Python 3.11; encontrado {version}. Revise environment.yml.",
    )


def revisar_entorno() -> Chequeo:
    conda = os.environ.get("CONDA_DEFAULT_ENV")
    if conda == "DriveGuardLab":
        return Chequeo("Entorno", "OK", "CONDA_DEFAULT_ENV=DriveGuardLab")
    if conda:
        return Chequeo(
            "Entorno",
            "AVISO",
            f"Activo '{conda}'; se esperaba 'DriveGuardLab'. Active el entorno correcto.",
        )
    prefijo = Path(sys.prefix)
    if (prefijo / "pyvenv.cfg").exists():
        detalle = f"Entorno virtual '{prefijo.name}' activo, no conda; se usan sus paquetes."
    else:
        detalle = f"Python del sistema en {prefijo}; no se detectó conda."
    if shutil.which("conda") is None:
        detalle += " conda no está en PATH."
    detalle += " Se esperaba el entorno DriveGuardLab."
    return Chequeo("Entorno", "AVISO", detalle)


def revisar_imports() -> list[Chequeo]:
    resultados: list[Chequeo] = []
    for nombre in IMPORTES_CLAVE:
        try:
            modulo = importlib.import_module(nombre)
            version = getattr(modulo, "__version__", "versión desconocida")
            resultados.append(Chequeo(f"Import {nombre}", "OK", str(version)))
        except Exception as exc:  # noqa: BLE001 - queremos cualquier fallo de import
            resultados.append(
                Chequeo(
                    f"Import {nombre}",
                    "ERROR",
                    f"{type(exc).__name__}: {cortar(exc, 110)}. No se instala nada; revise requirements.txt.",
                )
            )
    return resultados


def revisar_recursos() -> list[Chequeo]:
    resultados: list[Chequeo] = []
    if MODELO.is_file() and MODELO.stat().st_size > 0:
        resultados.append(
            Chequeo(
                "Modelo FaceLandmarker",
                "OK",
                f"{MODELO.relative_to(ROOT).as_posix()} ({MODELO.stat().st_size / 1e6:.1f} MB)",
            )
        )
    else:
        resultados.append(
            Chequeo(
                "Modelo FaceLandmarker",
                "ERROR",
                f"Falta {MODELO.relative_to(ROOT).as_posix()}. Ejecute python scripts/descargar_modelos.py",
            )
        )

    alarmas = sorted((ROOT / "assets").glob("alarma_*.wav"))
    if alarmas:
        detalle = ", ".join(
            f"{ruta.name} ({ruta.stat().st_size / 1000:.0f} kB)" for ruta in alarmas
        )
        resultados.append(Chequeo("Sonidos de alarma", "OK", detalle))
    else:
        resultados.append(
            Chequeo(
                "Sonidos de alarma",
                "ERROR",
                "No hay assets/alarma_*.wav. Ejecute python scripts/generar_recursos.py "
                "(sobrescribe los CSV de ejemplo).",
            )
        )
    return resultados


def revisar_config() -> Chequeo:
    estado = "Presente" if (ROOT / ".env").exists() else "Ausente"
    return Chequeo(
        ".env",
        "AVISO",
        f"{estado}; este script no lo lee ni lo imprime. Revise MONGO_URI, API_URL y "
        "NOTIFICACIONES_SIMULADAS en su terminal.",
    )


def puerto_abierto(host: str, puerto: int, espera: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, puerto), timeout=espera):
            return True
    except OSError:
        return False


def revisar_mongo() -> Chequeo:
    if puerto_abierto(MONGO_HOST, MONGO_PORT):
        return Chequeo(
            "MongoDB localhost:27017",
            "OK",
            f"Puerto TCP {MONGO_PORT} abierto (el estado real se confirma con /health).",
        )
    return Chequeo(
        "MongoDB localhost:27017",
        "AVISO",
        f"Puerto TCP {MONGO_PORT} cerrado o inalcanzable. MongoDB es opcional en runtime; "
        "confirme con /health cuando la API esté levantada.",
    )


def revisar_api() -> Chequeo:
    if not puerto_abierto("127.0.0.1", 8000):
        return Chequeo(
            "API /health",
            "AVISO",
            "API no levantada en 127.0.0.1:8000. Inicie: "
            "python -m uvicorn backend.main:app --reload --port 8000",
        )
    try:
        with urllib.request.urlopen(API_HEALTH, timeout=2.0) as respuesta:
            datos = json.load(respuesta)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Chequeo("API /health", "AVISO", f"No se pudo consultar: {cortar(exc, 110)}")
    mongo = datos.get("mongodb")
    return Chequeo(
        "API /health",
        "OK" if mongo else "AVISO",
        f"status={datos.get('status')}, mongodb={mongo}",
    )


def revisar_pytest() -> tuple[Chequeo, str]:
    try:
        proceso = subprocess.run(
            [sys.executable, "-m", "pytest"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return Chequeo("pytest", "ERROR", "Tiempo de espera agotado (10 min)."), ""
    salida = (proceso.stdout or "") + (proceso.stderr or "")
    lineas = salida.splitlines()
    resumen = next(
        (
            linea.strip()
            for linea in reversed(lineas)
            if " passed" in linea or " failed" in linea or " error" in linea or "no tests ran" in linea
        ),
        f"código de salida {proceso.returncode}",
    )
    detalle = f"código={proceso.returncode}; {cortar(resumen, 140)}"
    if proceso.returncode != 0:
        fallos = [linea for linea in lineas if linea.startswith(("FAILED", "ERROR"))][:8]
        if fallos:
            detalle += " | " + " | ".join(cortar(fallo, 110) for fallo in fallos)
    estado = "OK" if proceso.returncode == 0 else "ERROR"
    return Chequeo("pytest", estado, detalle), salida


def escribir_informe(chequeos: list[Chequeo], salida_pytest: str, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Diagnóstico del entorno — DriveGuard Lab",
        "",
        "Generado por `scripts/verificar_entorno.py` (sin instalar nada y sin leer `.env`).",
        "",
        "| Chequeo | Estado | Detalle |",
        "| --- | --- | --- |",
    ]
    for chequeo in chequeos:
        detalle = chequeo.detalle.replace("|", "\\|")
        lineas.append(f"| {chequeo.nombre} | {chequeo.estado} | {detalle} |")
    if salida_pytest:
        lineas += ["", "## Salida completa de pytest", "", "```text", salida_pytest.rstrip(), "```"]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sin-pytest", action="store_true", help="Omitir la suite pytest")
    parser.add_argument(
        "--informe", action="store_true", help=f"Guardar el diagnóstico en {INFORME.relative_to(ROOT)}"
    )
    args = parser.parse_args()

    chequeos: list[Chequeo] = [
        revisar_python(),
        revisar_entorno(),
        *revisar_imports(),
        *revisar_recursos(),
        revisar_config(),
        revisar_mongo(),
        revisar_api(),
    ]
    salida_pytest = ""
    if args.sin_pytest:
        chequeos.append(Chequeo("pytest", "AVISO", "Omitido con --sin-pytest"))
    else:
        chequeo_pytest, salida_pytest = revisar_pytest()
        chequeos.append(chequeo_pytest)

    print("DriveGuard Lab — verificación del entorno")
    print("=" * 72)
    for chequeo in chequeos:
        print(chequeo.linea())

    errores = [chequeo for chequeo in chequeos if chequeo.estado == "ERROR"]
    avisos = [chequeo for chequeo in chequeos if chequeo.estado == "AVISO"]
    if salida_pytest and any(c.estado == "ERROR" for c in chequeos if c.nombre == "pytest"):
        cola = salida_pytest.splitlines()[-15:]
        print("\nÚltimas líneas de pytest:")
        print("\n".join(cola))

    print("\n" + "=" * 72)
    print(f"Resumen: {len(chequeos) - len(errores) - len(avisos)} OK | "
          f"{len(avisos)} avisos | {len(errores)} errores")
    if args.informe:
        escribir_informe(chequeos, salida_pytest, INFORME)
        print(f"Informe guardado en {INFORME.relative_to(ROOT).as_posix()}")
    if errores:
        print("Corrija los errores anteriores antes de trabajar en el laboratorio.")
    elif avisos:
        print("Sin errores bloqueantes. Revise los avisos y confirme .env en su terminal.")
    else:
        print("Entorno listo.")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
