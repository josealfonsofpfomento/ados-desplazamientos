# ados-desplazamientos

JSON con los próximos desplazamientos de las unidades móviles de donación de sangre de ADOS (Sergas),
generado a partir de <https://ados.sergas.gal/cartafol/proximos-desprazamentos>.

Es la "API" que consume la app `ADOSMontecastelo`. No es un servicio oficial.

## URL de la API

Publicado con GitHub Pages (rama `main`, carpeta raíz):

```
https://josealfonsofpfomento.github.io/ados-desplazamientos/desplazamientos.json
```

Para Retrofit: `baseUrl = "https://josealfonsofpfomento.github.io/ados-desplazamientos/"` y
`@GET("desplazamientos.json")`. Tras un commit en `main`, Pages tarda uno o dos minutos en reflejar el cambio.

## Actualizar los datos

- **En GitHub:** pestaña *Actions* → *Actualizar desplazamientos* → *Run workflow*. Solo hace commit si hay cambios.
- **En local:** `pip install -r requirements.txt && python scripts/actualizar.py`

Si la web cambia de estructura el script falla y deja el JSON anterior intacto.

## Formato de `desplazamientos.json`

| Campo | Significado |
|---|---|
| `actualizado` | Fecha UTC de la última vez que cambiaron los datos |
| `desplazamientos[].id` | `fecha-concello[-n]`, estable |
| `fecha` | `AAAA-MM-DD` |
| `area` | Área sanitaria (zona para los avisos) |
| `concello`, `lugar`, `ubicacion` | Dónde está la unidad móvil. Los textos se normalizan (sin "Unidade móbil", en formato título) |
| `lat`, `lon` | Coordenadas del **centro del concello** (OpenStreetMap), no del punto exacto. `null` si no se encontraron |
| `horarios` | Lista de tramos `{desde, hasta}` (`HH:mm`); puede haber dos (mañana y tarde) |
| `horarioPorDeterminar` | `true` si la web dice "Horario a determinar" (`horarios` vacío) |
| `provisional` | `true` si la web marca el lugar como provisional |

## Coordenadas

El script geocodifica cada concello con Nominatim (OpenStreetMap) y guarda el resultado en `data/concellos.json`,
que actúa de caché: solo se consultan los concellos nuevos (1 petición por segundo, como exige su política de uso).
La precisión es de concello. Para llegar al punto exacto, la app abre Google Maps con la búsqueda
`"<lugar>, <concello>, Galicia"`.

Datos de mapas © colaboradores de OpenStreetMap (ODbL).
