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

1. **Comprobar quién es el dueño.** Con la URL actual de la API (la del dueño), en psql:
   `SELECT current_user;` tiene que dar el dueño de las tablas
   (`SELECT tableowner FROM pg_tables WHERE tablename = 'users';`). Si no coinciden,
   parar: los permisos por defecto del paso 2 serían de otro usuario.
2. **Crear el usuario.** En la misma sesión: `\i scripts/db/rol_de_la_api.sql` (se puede
   repetir) y `\password rydercup_app`. La contraseña se escribe en el aviso de psql y no
   se guarda en ningún fichero. Sin psql instalado:
   `docker run --rm -it -v "$PWD/scripts/db:/s:ro" postgres:16 psql "<URL del dueño>"` y
   `\i /s/rol_de_la_api.sql`.
3. **Render, primero sin cambiar nada:** añadir `MIGRATIONS_DATABASE_URL` con el valor
   ACTUAL de `DATABASE_URL` y desplegar. Todo sigue igual.
4. **Render, el cambio:** `DATABASE_URL` pasa a
   `postgresql://rydercup_app:<contraseña>@<mismo host>:5432/<misma base>` y desplegar.
   Mirar `/health`, entrar en la app y anotar algo de prueba en el Kind antes.
5. **Volver atrás:** `DATABASE_URL` con el valor de `MIGRATIONS_DATABASE_URL` y desplegar.

Las tablas que creen las migraciones futuras ya le dan permiso a `rydercup_app` solas (paso
4 del script). Las copias (`backup_ro`) y n8n no cambian.
