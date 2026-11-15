#!/usr/bin/env python3
"""Lee la tabla de https://ados.sergas.gal/cartafol/proximos-desprazamentos y genera desplazamientos.json.

Si la estructura de la web cambia y no se reconoce, el script falla SIN tocar el JSON anterior.
Solo reescribe el archivo (y la fecha `actualizado`) cuando los datos han cambiado.
"""
import json
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

URL = "https://ados.sergas.gal/cartafol/proximos-desprazamentos"
SALIDA = Path(__file__).resolve().parent.parent / "desplazamientos.json"
FECHA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
TRAMO = re.compile(r"(\d{2}:\d{2}) a (\d{2}:\d{2})")


def slug(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")


def nombre_area(crudo: str) -> str:
    """'A CORUÑA E CEE' -> 'A Coruña e CEE' (conectores en minúscula, siglas en mayúscula)."""
    minusculas, siglas = {"e", "de", "do", "da"}, {"CEE"}
    palabras = []
    for i, w in enumerate(crudo.split()):
        if w in siglas:
            palabras.append(w)
        elif i > 0 and w.lower() in minusculas:
            palabras.append(w.lower())
        else:
            palabras.append("-".join(p.capitalize() for p in w.split("-")))
    return " ".join(palabras)


def descargar(origen: str) -> str:
    if origen.startswith("http"):
        peticion = urllib.request.Request(origen, headers={"User-Agent": "ados-desplazamientos/1.0"})
        with urllib.request.urlopen(peticion, timeout=30) as r:
            return r.read().decode("utf-8")
    return Path(origen).read_text(encoding="utf-8")


def parsear(html: str) -> list[dict]:
    sopa = BeautifulSoup(html, "html.parser")
    grupos = sopa.select("details.group-details")
    if not grupos:
        raise ValueError("No se encontraron áreas sanitarias (¿cambió la web?)")
    resultado, vistos = [], {}
    for grupo in grupos:
        area = nombre_area(grupo.summary.get_text(strip=True).removeprefix("ÁREA SANITARIA").strip())
        fecha = None
        for nodo in grupo.select_one(".group-content").find_all(recursive=False):
            if "date-header" in nodo.get("class", []):
                m = FECHA.search(nodo.get_text())
                if not m:
                    raise ValueError(f"Fecha no reconocida: {nodo.get_text()!r}")
                fecha = f"{m[3]}-{m[2]}-{m[1]}"
            elif nodo.find("table"):
                if fecha is None:
                    raise ValueError("Tabla sin fecha previa")
                for fila in nodo.select("tbody tr"):
                    celdas = fila.find_all("td")
                    if len(celdas) != 3:
                        raise ValueError(f"Fila con {len(celdas)} celdas en {fecha}")
                    concello = celdas[0].get_text(strip=True)
                    lugar = celdas[1].find("strong").get_text(strip=True)
                    for item in celdas[2].select(".location-item"):
                        ubicacion = item.select_one(".location-name").get_text(" ", strip=True)
                        texto = item.select_one(".schedule-time").get_text(strip=True)
                        horarios = [{"desde": a, "hasta": b} for a, b in TRAMO.findall(texto)]
                        if not horarios and "determinar" not in texto.lower():
                            raise ValueError(f"Horario no reconocido: {texto!r}")
                        base = f"{fecha}-{slug(concello)}"
                        vistos[base] = vistos.get(base, 0) + 1
                        resultado.append({
                            "id": base if vistos[base] == 1 else f"{base}-{vistos[base]}",
                            "fecha": fecha,
                            "area": area,
                            "concello": concello,
                            "lugar": lugar,
                            "ubicacion": ubicacion,
                            "horarios": horarios,
                            "horarioPorDeterminar": not horarios,
                            "provisional": fila.select_one(".provisional-badge") is not None,
                        })
    if not resultado:
        raise ValueError("La tabla no contiene desplazamientos")
    return sorted(resultado, key=lambda d: (d["fecha"], d["area"], d["concello"], d["id"]))


def main() -> int:
    origen = sys.argv[1] if len(sys.argv) > 1 else URL
    try:
        nuevos = parsear(descargar(origen))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}. El JSON anterior no se ha modificado.", file=sys.stderr)
        return 1
    if SALIDA.exists():
        anteriores = json.loads(SALIDA.read_text(encoding="utf-8")).get("desplazamientos")
        if anteriores == nuevos:
            print(f"Sin cambios ({len(nuevos)} desplazamientos).")
            return 0
    doc = {
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": URL,
        "desplazamientos": nuevos,
    }
    SALIDA.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Actualizado: {len(nuevos)} desplazamientos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
