# Docker Setup - Ryder Cup Backend

## Quick Start

1. **Configurar variables de entorno**:
   ```bash
   cp docker/.env.example docker/.env
   # Edita docker/.env con tus valores
   ```

2. **Iniciar servicios**:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

3. **Aplicar migraciones**:
   ```bash
   docker exec docker-app-1 alembic upgrade head
   ```

4. **Verificar servicios**:
   ```bash
   docker-compose -f docker/docker-compose.yml ps
   ```

## Servicios

- **PostgreSQL**: `localhost:5433` (evita conflicto con K8s en 5434)
- **FastAPI**: `localhost:8001` (evita conflicto con K8s en 8000)
- **Swagger UI**: `http://localhost:8001/docs`

## Configuración

Las variables de entorno específicas de Docker están en `docker/.env`:
- `DOCKER_DATABASE_PORT=5433` (vs K8s: 5434)
- `DOCKER_APP_PORT=8001` (vs K8s: 8000)

Para K8s, ver `.env` en la raíz del proyecto.

## Comandos Útiles

```bash
# Ver logs
docker-compose -f docker/docker-compose.yml logs -f

# Reiniciar con rebuild
docker-compose -f docker/docker-compose.yml down && \
docker-compose -f docker/docker-compose.yml up -d --build

# Acceder a PostgreSQL
docker exec -it docker-db-1 psql -U rydercupam_adminuser -d rcfdevdb

# Limpiar todo (incluye volúmenes)
docker-compose -f docker/docker-compose.yml down -v
```

## Troubleshooting

**Error: port already allocated**
- Docker y K8s usan puertos diferentes. Verifica que no haya conflictos.
- Docker: 5433 (db), 8001 (app)
- K8s: 5434 (db), 8000 (app)

**Error: MISSING_USER/MISSING_PASSWORD**
- Asegúrate de haber creado `docker/.env` desde `docker/.env.example`
- Verifica que las variables `POSTGRES_*` estén definidas
