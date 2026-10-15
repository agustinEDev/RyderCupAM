# Datos de OpenStreetMap para tests

`valderrama.geojsonseq`: un extracto de los contornos de campo, hoyos y greens a
menos de 2,5 km de Valderrama, sacado del `osmium export -f geojsonseq
--attributes=type,id` del volcado de España de Geofabrik (14 oct 2026), tras
`osmium tags-filter`. Va una línea por objeto, sin el separador RS que osmium pone
delante de cada uno (el cliente acepta los dos).

© OpenStreetMap contributors. Datos bajo licencia ODbL
(https://opendatacommons.org/licenses/odbl/).
