#!/usr/bin/env python3
"""Lee la tabla de https://ados.sergas.gal/cartafol/proximos-desprazamentos y genera desplazamientos.json.

Si la estructura de la web cambia y no se reconoce, el script falla SIN tocar el JSON anterior.
Solo reescribe el archivo (y la fecha `actualizado`) cuando los datos han cambiado.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

URL = "https://ados.sergas.gal/cartafol/proximos-desprazamentos"
RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "desplazamientos.json"
CACHE = RAIZ / "data" / "concellos.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
GALICIA = (41.7, 43.9, -9.4, -6.6)  # lat mín, lat máx, lon mín, lon máx
PREFIJO_UNIDAD = re.compile(r"^(UNIDADE\s+M[ÓO][BV]IL|UM)\s+", re.IGNORECASE)
FECHA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
TRAMO = re.compile(r"(\d{2}:\d{2}) a (\d{2}:\d{2})")


def slug(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")


MENORES = {"a", "o", "as", "os", "e", "de", "do", "da", "dos", "das", "en", "na", "no", "nas", "nos",
           "ao", "á", "ás", "ó", "ós", "con", "por", "para", "entre", "sobre", "xunto", "diante", "detrás",
           "carón", "n", "s", "do"}


def mayusculas(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.8


def a_titulo(texto: str) -> str:
    """'PRAZA IRMÁNS GARCÍA NAVEIRA' -> 'Praza Irmáns García Naveira' (preposiciones en minúscula)."""
    def palabra(m: re.Match) -> str:
        w = m[0].lower()
        return w if m.start() > 0 and w in MENORES else w.capitalize()
    return re.sub(r"[^\W\d_]+", palabra, texto)


def limpiar(texto: str, quitar_unidad: bool = False) -> str:
    """Normaliza espacios y saltos de línea, quita 'Unidade móbil' y pasa a título lo que venía en MAYÚSCULAS."""
    texto = re.sub(r"\s+", " ", texto).strip()
    if quitar_unidad:
        texto = PREFIJO_UNIDAD.sub("", texto)
    if mayusculas(texto):
        texto = a_titulo(texto)
    return texto[:1].upper() + texto[1:]


def titulo(texto: str) -> str:
    texto = re.sub(r"\s+", " ", texto).strip()
    return a_titulo(texto) if mayusculas(texto) else texto


def geocodificar(concello: str) -> dict | None:
    """Centro del concello según OpenStreetMap (Nominatim). None si no se encuentra dentro de Galicia."""
    url = NOMINATIM + "?" + urllib.parse.urlencode(
        {"q": f"{concello}, Galicia, Spain", "format": "jsonv2", "limit": 5, "countrycodes": "es"})
    peticion = urllib.request.Request(url, headers={"User-Agent": "ados-desplazamientos/1.0"})
    with urllib.request.urlopen(peticion, timeout=30) as r:
        resultados = json.loads(r.read().decode("utf-8"))
    # "Ourense" o "Lugo" también existen como provincia/comarca: solo vale un núcleo o municipio.
    for tipo in ("municipality", "city", "town", "village"):
        elegido = next((r for r in resultados if r.get("addresstype") == tipo), None)
        if elegido:
            break
    else:
        return None
    lat, lon = float(elegido["lat"]), float(elegido["lon"])
    if not (GALICIA[0] <= lat <= GALICIA[1] and GALICIA[2] <= lon <= GALICIA[3]):
        return None
    return {"lat": round(lat, 5), "lon": round(lon, 5)}


def añadir_coordenadas(desplazamientos: list[dict], geocodificar_nuevos: bool) -> None:
    """Rellena lat/lon (centro del concello) usando data/concellos.json como caché; solo consulta los que faltan."""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    consultas = 0
    for concello in sorted({d["concello"] for d in desplazamientos} - cache.keys()):
        if not geocodificar_nuevos:
            continue
        if consultas:
            time.sleep(1.1)  # política de uso de Nominatim: 1 petición por segundo
        consultas += 1
        try:
            punto = geocodificar(concello)
        except Exception as e:  # noqa: BLE001
            print(f"AVISO: no se pudo geocodificar {concello!r}: {e}", file=sys.stderr)
            continue
        if punto is None:
            print(f"AVISO: {concello!r} sin coordenadas válidas en Galicia", file=sys.stderr)
            continue
        cache[concello] = punto
    if consultas:
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for d in desplazamientos:
        punto = cache.get(d["concello"])
        d["lat"], d["lon"] = (punto["lat"], punto["lon"]) if punto else (None, None)


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
                    lugar = titulo(celdas[1].find("strong").get_text(strip=True))
                    for item in celdas[2].select(".location-item"):
                        ubicacion = limpiar(item.select_one(".location-name").get_text(" ", strip=True), quitar_unidad=True)
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    origen = args[0] if args else URL
    try:
        nuevos = parsear(descargar(origen))
        añadir_coordenadas(nuevos, geocodificar_nuevos="--sin-geocodificar" not in sys.argv)
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
