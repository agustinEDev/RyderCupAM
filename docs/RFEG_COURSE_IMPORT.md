# Importación de campos federados

Cómo cargar en la base de datos los 802 recorridos que publica la Real
Federación Española de Golf, y qué mirar antes de aplicarlo en producción.

## Lo que hace

`scripts/import_golf_courses.py` lee el volcado que viaja en el repositorio
(`data/rfeg_dataset.json.gz`) y da de alta cada recorrido **llamando a los casos
de uso**, no escribiendo en las tablas. Así los 802 campos pasan por las mismas
invariantes que un alta hecha desde la aplicación: un dato imposible se rechaza
en vez de quedarse guardado.

Un recorrido de la federación es un campo de la aplicación. Los campos quedan
aprobados directamente y su autor es una cuenta de sistema desactivada, no una
persona.

## Cómo se usa

```bash
# Pasada en seco: no toca nada, cuenta qué haría
python scripts/import_golf_courses.py

# Aplica solo las altas nuevas
python scripts/import_golf_courses.py --apply

# Aplica además las coincidencias que necesitan visto bueno
python scripts/import_golf_courses.py --apply --confirm-merges

# Pruebas rápidas con unos pocos recorridos
python scripts/import_golf_courses.py --limit 20
```

La base de datos es la de `DATABASE_URL`. La carga completa tarda unos quince
segundos contra PostgreSQL local.

## Antes de tocar producción

1. **Desplegar primero el backend.** Las columnas de ubicación y procedencia
   llegan en las migraciones `c4d8e1a72b93` y `e7f2b3c9d418`, que Render aplica
   al arrancar. Importar contra una base sin ellas falla al instante.
2. **Pasada en seco y leerla entera.** Interesa sobre todo el apartado de
   coincidencias que piden confirmación: son los campos que el importador cree
   reconocer pero no está seguro.
3. **Decidir una por una** esas coincidencias. Se aplican con `--confirm-merges`,
   que es una decisión consciente, no el comportamiento por defecto.
4. **Aplicar.** Reejecutar es seguro: lo ya importado se actualiza, no se
   duplica.

## Cómo reconoce un campo que ya existe

Por orden, de la prueba más fuerte a la más débil:

| Señal | Qué significa | Se aplica |
|---|---|---|
| Mismo identificador externo | El mismo recorrido de la misma fuente | Sí, automáticamente |
| Mismo club, misma tarjeta, otro identificador | La federación lo ha renombrado | Solo con `--confirm-merges` |
| Alta manual con el mismo nombre, o al lado con la misma tarjeta | El campo ya estaba dado de alta a mano | Solo con `--confirm-merges` |
| Más de un candidato | Ambiguo | No: se trata como campo nuevo |

El identificador externo es el id del club en la federación más el nombre del
recorrido tal como lo publica la fuente, normalizado: `915:GOLF DE DERIO P P`.

Dos decisiones que conviene entender:

- **No se usa el `way_id` de la RFEG**, que sería lo natural, porque identifica
  cada salida y no el recorrido: en 800 de los 802 recorridos hay un `way_id`
  distinto por cada barra.
- **No se usa el nombre que mostramos**, sino el de origen, porque el nuestro
  depende de las tablas de tildes y capitalización. Cambiar una tilde convertiría
  los 802 campos en desconocidos en la siguiente importación.

Ante la duda, el importador prefiere crear un campo nuevo: duplicar tiene
arreglo, sobrescribir el campo equivocado con los datos de otro no.

## Los nombres

La federación publica en mayúsculas, a menudo sin tildes, y antepone el club
solo a veces. El importador:

- Restaura **42 tildes** de una tabla revisada a mano
  (`src/modules/golf_course/infrastructure/importers/name_accents.json`). Añadir
  una corrección es añadir una línea, sin tocar código.
- Respeta las siglas: `P&P`, `R.C.I.`, `RCG` no se convierten en `P&p` ni en
  `R.c.i.`.
- Antepone el club **solo en los 18 recorridos** cuyo nombre no lo menciona, para
  que buscar por el club los encuentre.
- Deshace el artículo pospuesto de las localidades: `CALA DE MIJAS, LA` queda
  como `La Cala de Mijas`.

## Campos de nueve hoyos

La federación publica siempre tarjeta de 18, así que un campo de nueve aparece
con la vuelta repetida. Se marcan **342 recorridos** combinando dos señales,
porque ninguna basta sola:

- Lo que la federación declara del club. Por sí sola deja fuera 148 pitch & putt
  y circuitos cortos anexos a campos de 18 o 27 hoyos.
- Que la ida y la vuelta sean idénticas en par y en metros. Por sí sola deja
  fuera 83 campos de nueve reales, los que juegan la segunda vuelta desde otras
  barras.

## Actualizar el volcado

El extractor vive en un proyecto aparte (`rfeg-courses-import`). Para cargar una
extracción nueva:

```bash
gzip -c ruta/al/rfeg_dataset.json > data/rfeg_dataset.json.gz
python scripts/import_golf_courses.py            # pasada en seco
```

El importador rechaza un fichero que no parezca una extracción de la RFEG antes
de recorrer nada, para no darse cuenta a mitad de la carga.
