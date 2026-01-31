# Docker Setup - Ryder Cup Backend

## Quick Start

1. **Configurar variables de entorno**:
   ```bash
   cp docker/.env.example docker/.env
   # Edita docker/.env con tus valores
   ```

2. **Iniciar servicios**:
   ```bash
   docker-compose -f docker/docker-compose.yml --env-file docker/.env up -d
   ```

   **IMPORTANTE**: El flag `--env-file docker/.env` es necesario para que docker-compose interpole las variables de puerto en el docker-compose.yml.

3. **Aplicar migraciones**:
   ```bash
   docker exec docker-app-1 alembic upgrade head
   ```

4. **Verificar servicios**:
   ```bash
   docker-compose -f docker/docker-compose.yml --env-file docker/.env ps
   ```

## Servicios

- **PostgreSQL**: `localhost:5433` (evita conflicto con K8s en 5434)
- **FastAPI**: `localhost:8000` (puerto estándar del proyecto)
- **Swagger UI**: `http://localhost:8000/docs`

## Configuración

Las variables de entorno específicas de Docker están en `docker/.env`:
- `DOCKER_DATABASE_PORT=5433` (vs K8s: 5434)
- `DOCKER_APP_PORT=8000` (puerto estándar, cambia a 8001 si usas K8s simultáneamente)

Para K8s, ver `.env` en la raíz del proyecto.

**Nota**: Si necesitas correr Docker y K8s simultáneamente, cambia `DOCKER_APP_PORT=8001` en `docker/.env`.

## Comandos Útiles

```bash
# Ver logs
docker-compose -f docker/docker-compose.yml --env-file docker/.env logs -f

# Reiniciar con rebuild
docker-compose -f docker/docker-compose.yml --env-file docker/.env down && \
docker-compose -f docker/docker-compose.yml --env-file docker/.env up -d --build

# Acceder a PostgreSQL
docker exec -it docker-db-1 psql -U rydercupam_adminuser -d rcfdevdb

# Limpiar todo (incluye volúmenes)
docker-compose -f docker/docker-compose.yml --env-file docker/.env down -v
```

## Troubleshooting

**Error: port already allocated (8000)**
- Si K8s está corriendo, cambia `DOCKER_APP_PORT=8001` en `docker/.env`
- Verifica si K8s está activo: `docker ps | grep kindest`
- Para detener K8s: `kind delete cluster --name rydercupam-cluster`
- Puertos por defecto:
  - Docker: 5433 (db), 8000 (app)
  - K8s: 5434 (db), 8000 (app) ← conflicto
- Solución: usar DOCKER_APP_PORT=8001 cuando ambos corren simultáneamente

**Error: port already allocated (5433)**
- El puerto 5433 ya está en uso por otro proceso
- Verifica: `lsof -i :5433`

**Error: MISSING_USER/MISSING_PASSWORD**
- Asegúrate de haber creado `docker/.env` desde `docker/.env.example`
- Verifica que las variables `POSTGRES_*` estén definidas
