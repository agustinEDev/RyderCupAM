# 🚀 Runbook - Operaciones

## Deployment

### Local Development
```bash
docker-compose up -d
docker-compose exec app alembic upgrade head
```

### Production
```bash
# 1. Build
docker build -t ryderclub:latest .

# 2. Deploy
docker-compose -f docker-compose.prod.yml up -d

# 3. Migrations
docker-compose exec app alembic upgrade head

# 4. Health check
curl https://api.ryderclub.com/health
```

### Rollback
```bash
# Rollback migration
docker-compose exec app alembic downgrade -1

# Rollback deploy
docker-compose up -d ryderclub:<previous-tag>
```

## Monitoreo

### Métricas Clave
- **Uptime**: > 99.9%
- **Response Time**: < 200ms (p95)
- **Error Rate**: < 0.1%

### Logs
```bash
# Application logs
docker-compose logs -f --tail=100 app

# Database logs
docker-compose logs -f db

# Filtrar errores
docker-compose logs app | grep ERROR
```

### Health Checks
```bash
# App status
curl http://localhost:8000/

# DB status
docker-compose exec db psql -U postgres -c "SELECT 1"
```

## Troubleshooting

### Servicio No Responde
```bash
# 1. Verificar estado
docker-compose ps

# 2. Revisar logs
docker-compose logs app --tail=50

# 3. Reiniciar
docker-compose restart app

# 4. Si persiste
docker-compose down
docker-compose up -d
```

### BD Connection Failed
```bash
# 1. Verificar PostgreSQL
docker-compose ps db

# 2. Test connection
docker-compose exec db psql -U postgres

# 3. Verificar env vars
cat .env | grep DATABASE_URL

# 4. Rebuild
docker-compose down -v
docker-compose up -d
```

### Tests Failing en CI/CD
```bash
# 1. Limpiar cache
pytest --cache-clear

# 2. Rebuild test DB
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d

# 3. Run tests
python dev_tests.py
```

### Migrations Issues
```bash
# Ver estado actual
alembic current

# Ver historial
alembic history

# Rollback y retry
alembic downgrade -1
alembic upgrade head
```

## Backups

### Database Backup
```bash
# Crear backup
docker-compose exec db pg_dump -U postgres ryderclub > backup_$(date +%Y%m%d).sql

# Restaurar
docker-compose exec -T db psql -U postgres ryderclub < backup_20251109.sql
```

## Performance

### Optimización
- Índices en `users(email)`
- Connection pooling: max 20 connections
- Timeout RFEG: 10s

### Monitoreo
- Queries lentas: > 100ms
- Pool exhaustion: alertar si > 18 conexiones
- RFEG failures: alertar si > 10% error rate
