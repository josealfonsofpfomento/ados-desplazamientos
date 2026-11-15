# ados-desplazamientos

JSON con los próximos desplazamientos de las unidades móviles de donación de sangre de ADOS (Sergas),
generado a partir de <https://ados.sergas.gal/cartafol/proximos-desprazamentos>.

Es la "API" que consume la app `ADOSMontecastelo`. No es un servicio oficial.

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
| `concello`, `lugar`, `ubicacion` | Dónde está la unidad móvil |
| `horarios` | Lista de tramos `{desde, hasta}` (`HH:mm`); puede haber dos (mañana y tarde) |
| `horarioPorDeterminar` | `true` si la web dice "Horario a determinar" (`horarios` vacío) |
| `provisional` | `true` si la web marca el lugar como provisional |
