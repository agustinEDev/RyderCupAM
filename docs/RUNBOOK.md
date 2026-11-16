# 🚀 Runbook - RyderCup AM

## Deployment

### Docker (Local)
```bash
# Setup
docker-compose up -d
docker-compose exec app alembic upgrade head

# Rebuild
docker-compose up -d --build app

# Reset
docker-compose down -v && docker-compose up -d
```

### Kubernetes (Producción)
```bash
# Deploy completo
./k8s/scripts/deploy-cluster.sh

# Actualizar backend
./k8s/scripts/deploy-api.sh [version]

# Actualizar frontend
./k8s/scripts/deploy-front.sh

# Deploy DB + migraciones
./k8s/scripts/deploy-db.sh

# Estado del cluster
./k8s/scripts/cluster-status.sh

# Destruir cluster
./k8s/scripts/destroy-cluster.sh
```

### Render: paquetes del sistema de la imagen al día (INF-02)

Render construye la imagen con su propia caché de capas y no pasa `APT_REFRESH` (el CI le
pasa el día, Render nada): la capa del `apt-get upgrade` del Dockerfile se queda como la
primera vez que la construyó. Hacer **Manual Deploy → «Clear build cache & deploy»** en el
servicio del backend cuando:

- cambie `docker/Dockerfile` (digest de la imagen base incluido), y
- Trivy (pestaña Security o la puerta del CI) avise de un paquete del sistema con arreglo.

Es el mismo despliegue de siempre, solo que sin caché: tarda unos minutos más.

### Comandos kubectl Esenciales
```bash
# Pods y estado
kubectl get pods -n rydercup
kubectl describe pod -n rydercup <pod-name>
kubectl get events -n rydercup --sort-by='.lastTimestamp'

# Shell en pod
kubectl exec -it -n rydercup deployment/api-deployment -- bash
kubectl exec -it -n rydercup deployment/postgres -- psql -U postgres -d rydercup

# Escalar
kubectl scale deployment api-deployment -n rydercup --replicas=3

# Rollback
kubectl rollout undo deployment/api-deployment -n rydercup

# Port forwarding
kubectl port-forward -n rydercup svc/api-service 8000:8000
kubectl port-forward -n rydercup svc/frontend-service 3000:80
kubectl port-forward -n rydercup svc/postgres 5432:5432
```

---

## Logs

### Docker
```bash
# Tiempo real
docker-compose logs -f app
docker-compose logs -f --tail=100 app

# Filtrar
docker-compose logs app | grep ERROR
docker-compose logs app --since 5m
docker-compose logs app > logs/app_$(date +%Y%m%d_%H%M%S).log
```

### Kubernetes
```bash
# Tiempo real
kubectl logs -f -n rydercup deployment/api-deployment
kubectl logs -f -n rydercup deployment/postgres
kubectl logs -f -n rydercup deployment/api-deployment --tail=50

# Filtrar
kubectl logs -n rydercup deployment/api-deployment --since=5m
kubectl logs -n rydercup deployment/api-deployment | grep ERROR
kubectl logs -n rydercup -l app=api --tail=100 --timestamps=true

# Pod específico
kubectl logs -n rydercup <pod-name>
kubectl logs -n rydercup <pod-name> --previous

# Guardar
kubectl logs -n rydercup deployment/api-deployment > logs/k8s_api_$(date +%Y%m%d_%H%M%S).log

# Eventos
kubectl get events -n rydercup --sort-by='.lastTimestamp'
kubectl get events -n rydercup --field-selector type!=Normal

# Logs de aplicación
kubectl exec -it -n rydercup deployment/api-deployment -- tail -f logs/security_audit.log
```

---

## Troubleshooting

### Docker
```bash
# Servicio no responde
docker-compose ps
docker-compose logs app --tail=100
docker-compose restart app
docker-compose down && docker-compose up -d --build

# DB connection
docker-compose exec db psql -U postgres
docker-compose down -v && docker-compose up -d

# Port ocupado
lsof -i :8000
kill -9 <PID>
```

### Kubernetes
```bash
# Pod crasheando
kubectl logs -n rydercup <pod-name> --previous
kubectl describe pod -n rydercup <pod-name>

# ImagePullBackOff
kubectl describe pod -n rydercup <pod-name>
kubectl rollout restart deployment/api-deployment -n rydercup

# Service no accesible
kubectl get svc -n rydercup
kubectl get endpoints -n rydercup
kubectl port-forward -n rydercup svc/api-service 8000:8000

# PVC issues
kubectl get pvc -n rydercup
kubectl describe pvc postgres-pvc -n rydercup
```

### Migraciones
```bash
# Docker
docker-compose exec app alembic current
docker-compose exec app alembic history
docker-compose exec app alembic upgrade head
docker-compose exec app alembic downgrade -1

# Kubernetes
kubectl exec -it -n rydercup deployment/api-deployment -- alembic current
kubectl exec -it -n rydercup deployment/api-deployment -- alembic upgrade head
kubectl exec -it -n rydercup deployment/api-deployment -- alembic downgrade -1
```

---

## Backups

### Docker
```bash
# Crear
docker-compose exec db pg_dump -U postgres rydercup > k8s/backups/db_backup_$(date +%Y%m%d_%H%M%S).sql
docker-compose exec db pg_dump -U postgres rydercup | gzip > k8s/backups/db_backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restaurar
docker-compose exec -T db psql -U postgres rydercup < k8s/backups/db_backup_20260128.sql
gunzip < k8s/backups/db_backup_20260128.sql.gz | docker-compose exec -T db psql -U postgres rydercup
```

### Kubernetes
```bash
# Crear
kubectl exec -n rydercup deployment/postgres -- pg_dump -U postgres rydercup > k8s/backups/k8s_backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar
./k8s/scripts/restore-db.sh k8s/backups/k8s_backup_20260128.sql
kubectl exec -i -n rydercup deployment/postgres -- psql -U postgres rydercup < k8s/backups/k8s_backup_20260128.sql
```

### Backup Automático (Cronjob)
```bash
# Añadir a crontab: crontab -e
0 2 * * * cd /path/to/project && docker-compose exec db pg_dump -U postgres rydercup | gzip > k8s/backups/auto_backup_$(date +\%Y\%m\%d).sql.gz

# Limpiar backups antiguos (>7 días)
find k8s/backups/ -name "auto_backup_*.sql.gz" -mtime +7 -delete
```

---

## Monitoreo

### Health Checks
```bash
# Docker
curl http://localhost:8000/
docker-compose ps

# Kubernetes
kubectl get pods -n rydercup
kubectl top pods -n rydercup
kubectl top nodes
```

### Performance
```bash
# Docker
docker stats

# Kubernetes
kubectl top pods -n rydercup
kubectl top nodes
kubectl describe pod -n rydercup <pod-name> | grep -A 5 "Limits"

# Query performance
docker-compose exec db psql -U postgres rydercup -c "EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com';"
```

---

## Quick Reference

### Comandos Frecuentes
```bash
# Docker
docker-compose up -d
docker-compose logs -f app
docker-compose ps
docker-compose restart app
docker-compose down -v

# Kubernetes
./k8s/scripts/deploy-cluster.sh
./k8s/scripts/deploy-api.sh
kubectl get pods -n rydercup
kubectl logs -f -n rydercup deployment/api-deployment
kubectl exec -it -n rydercup deployment/api-deployment -- bash
```

### URLs
- Docker Backend: http://localhost:8000
- Docker Docs: http://localhost:8000/docs
- Docker PostgreSQL: localhost:5432
- K8s (port-forward): kubectl port-forward -n rydercup svc/api-service 8000:8000

## Usuario de la API sin permisos de estructura (DB-01)

La API puede entrar con `rydercup_app`, que solo lee y escribe filas; las migraciones del
arranque entran con el dueño de la base. Sin `MIGRATIONS_DATABASE_URL` todo funciona como
antes (las migraciones usan `DATABASE_URL`).

Ninguna contraseña va en la línea de órdenes (quedaría en el historial y en `ps`): psql la
pide en su aviso.

1. **Entrar como el dueño.** Con los datos de la URL actual de la API, SIN la contraseña:
   `psql "host=<host> port=5432 dbname=<base> user=<usuario> sslmode=require"`. Sin psql
   instalado: `docker run --rm -it -v "$PWD/scripts/db:/s:ro" postgres:15 psql "<lo mismo>"`.
2. **Comprobar quién es el dueño.** `SELECT current_user;` tiene que dar el dueño de las
   tablas (`SELECT tableowner FROM pg_tables WHERE tablename = 'users';`). Si no
   coinciden, parar: los permisos por defecto serían de otro usuario.
3. **Crear el usuario.** `\set ON_ERROR_STOP on` y luego `\i scripts/db/rol_de_la_api.sql`
   (o `\i /s/rol_de_la_api.sql` con Docker). Va en una transacción: si algo falla no
   cambia nada. Se puede repetir y se niega si la base no está migrada. Después,
   `\password rydercup_app`. El script también quita a `n8n_lectura` la lectura automática
   de las tablas futuras (DB-03); sus permisos sobre las de hoy los recorta
   `scripts/db/rol_de_n8n.sql` (sección siguiente).
4. **Render, primero sin cambiar nada:** añadir `MIGRATIONS_DATABASE_URL` con el valor
   ACTUAL de `DATABASE_URL` y desplegar. Todo sigue igual.
5. **Render, el cambio:** `DATABASE_URL` pasa a
   `postgresql://rydercup_app:<contraseña>@<mismo host>:5432/<misma base>`, con la
   contraseña codificada para URL si lleva `@ : / # ? %` (mejor elegir una sin ellos), y
   desplegar. Mirar `/health` y entrar en la app. Antes, todo esto en el Kind.
6. **Volver atrás:** `DATABASE_URL` con el valor de `MIGRATIONS_DATABASE_URL` y desplegar.

Las tablas que creen las migraciones futuras ya le dan permiso a `rydercup_app` solas (paso
4 del script). `backup_ro` las lee por un permiso por defecto que ya tiene en producción y
que el script no toca: comprobarlo antes del cambio con `\ddp` (tiene que salir
`backup_ro=r` en las tablas del dueño); si no sale, las copias no llevarían las tablas
nuevas.

## n8n solo lee lo del informe (DB-01)

`n8n_lectura` es el usuario con el que n8n saca el informe de los lunes. Tenía `SELECT` en
42 de las 43 tablas (también `users` con los hashes, `refresh_tokens`, `password_history`).
`scripts/db/rol_de_n8n.sql` le quita todo y le deja solo las columnas que lee la consulta
del informe (`~/n8n-cbg/workflows/informe-semanal.json`, nodo «Datos de la app (solo
lectura)»), solo lectura y con tiempos límite.

1. **Entrar como el dueño**, como en la sección anterior (pasos 1 y 2).
2. `\set ON_ERROR_STOP on` y `\i scripts/db/rol_de_n8n.sql`. Va en una transacción y
   comprueba el resultado antes del `COMMIT`: si sale «conserva permisos de tabla entera»,
   esos permisos los dio otro usuario (el `REVOKE` solo quita los que dio quien lo
   ejecuta) y no ha cambiado nada; ejecutarlo como ese usuario.
3. **Mirar las consultas del final:** ninguna tabla entera legible, exactamente las 11
   columnas, `false` en hashes, correos, `refresh_tokens` y `password_history`, y los
   cuatro ajustes del rol (`default_transaction_read_only=on`, `statement_timeout=30s`,
   `idle_in_transaction_session_timeout=60s`, `lock_timeout=5s`).
4. **Probar el informe sin mandarlo:** en n8n, abrir el flujo del informe y ejecutar solo
   el nodo «Datos de la app (solo lectura)». Tiene que devolver una fila con los números.
5. **Volver atrás no hace falta para el informe:** si el paso 4 falla con «permission
   denied for ... column X», el informe ha pasado a leer una columna nueva; se añade al
   script (pasos 3 y 5) y se vuelve a ejecutar. Nunca devolver la tabla entera: un
   `GRANT SELECT ON public.users` vuelve a dar el hash, el correo y el token de reseteo.

## Restaurar producción (DB-03)

Para cuando la base de Render se pierde o se corrompe. La copia diaria del Mac
(`~/.local/bin/copia_pro.sh`, 03:30, en `~/Backups/rydercup-pro`) es `pg_dump -Fc
--no-owner --no-privileges`: trae tablas, datos y la versión de Alembic, pero **ni dueños,
ni permisos, ni usuarios, ni sus ajustes**. Restaurarla sin más deja a la API
(`rydercup_app`), a la copia (`backup_ro`) y a n8n (`n8n_lectura`) sin poder leer nada.
El orden importa.

Ninguna contraseña va en la línea de órdenes: psql y pg_restore la piden en su aviso.

1. **Parar las escrituras.** En Render, suspender el servicio de la API: lo que se
   escriba mientras tanto se perdería al restaurar.
2. **Elegir la copia.** La más reciente que esté bien: `pg_restore --list <copia>.dump |
   grep -c 'TABLE DATA'` tiene que dar el número de tablas de siempre (38 a 17 nov 2026,
   más las que hayan añadido las migraciones).
3. **La base de destino.** Si la de Render sigue viva, usar la misma (pasos 4 en adelante
   sobre ella). Si hay que crear otra: Postgres **15**, misma región; su usuario por
   defecto será el nuevo dueño.
4. **Restaurar como el dueño**, sin dueños ni permisos de la copia:
   `pg_restore --no-owner --no-privileges --clean --if-exists -d "host=<host> port=5432
   dbname=<base> user=<dueño> sslmode=require" <copia>.dump`. Con `--clean` borra lo que
   haya antes de cargar; en una base nueva no hace falta. Tiene que acabar sin errores
   (los avisos de «does not exist» del `--clean` en una base vacía no lo son).
5. **Comprobar la versión del esquema.** `SELECT version_num FROM alembic_version;` tiene
   que ser la de la release desplegada. Si es anterior, el arranque de la API migrará
   solo; si es posterior, la API desplegada no entiende el esquema: desplegar la release
   que corresponde.
6. **Los usuarios y sus permisos**, en psql como el dueño y con `\set ON_ERROR_STOP on`:
   - `\i scripts/db/rol_de_la_api.sql` y `\password rydercup_app` (sección «Usuario de
     la API sin permisos de estructura»). En una base nueva el usuario no existe y se crea.
   - `\i scripts/db/rol_de_n8n.sql` (sección «n8n solo lee lo del informe»).
   - `\i scripts/db/ajustes_de_la_base.sql`: tiempos límite de `rydercup_app`, sin
     tablas temporales ni creación en `public` para nadie más.
   - `backup_ro` (no tiene script): `GRANT CONNECT ON DATABASE <base> TO backup_ro;`,
     `GRANT USAGE ON SCHEMA public TO backup_ro;`, `GRANT SELECT ON ALL TABLES IN SCHEMA
     public TO backup_ro;`, `GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO
     backup_ro;`, `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO
     backup_ro;` y `ALTER ROLE backup_ro SET default_transaction_read_only = on;`. En una
     base nueva, crearlo antes con `CREATE ROLE backup_ro LOGIN` y `\password backup_ro`.
7. **Render.** Si la base es nueva: `DATABASE_URL` con `rydercup_app` y
   `MIGRATIONS_DATABASE_URL` con el dueño, los dos al host nuevo; en el Llavero del Mac,
   la URL de `backup_ro` (servicio `rydercup-pro-backup`, desde la app Terminal); y la
   conexión de n8n. Reanudar la API.
8. **Comprobar.** `curl https://api.rydercupfriends.com/health`, entrar en la app y ver un
   torneo. Lanzar `~/.local/bin/copia_pro.sh` a mano: tiene que acabar bien. Ejecutar en
   n8n solo el nodo «Datos de la app (solo lectura)».

**Pendiente:** probarlo entero una vez contra una base de usar y tirar (la auditoría lo
pide). La restauración de los datos ya se probó el 17 oct 2026 (86 146 filas idénticas);
los pasos 6 y 7 no.
