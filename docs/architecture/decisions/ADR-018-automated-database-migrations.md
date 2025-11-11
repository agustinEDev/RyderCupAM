# ADR-018: Automated Database Migrations in Production

**Estado**: ✅ Aceptado
**Fecha**: 11 Nov 2025

---

## Contexto

Necesitamos sincronizar schema de base de datos con código en cada deployment a producción.

**Problema**: Migraciones manuales son propensas a errores y requieren intervención humana en deploys.

**Alternativas**:
1. **Manual Migrations**: Ejecutar `alembic upgrade head` manualmente vía SSH/Shell
2. **Separate CD Pipeline**: Migrations como step independiente antes de deploy
3. **Automated in Entrypoint**: Migrations ejecutadas automáticamente al iniciar app
4. **Blue-Green Deployment**: Migrations en pre-deploy hook

---

## Decisión

**Ejecutar migraciones automáticamente en `entrypoint.sh` antes de iniciar la aplicación.**

### Implementación (`entrypoint.sh`):

```bash
#!/bin/bash
set -e

echo "🚀 Iniciando Ryder Cup Manager API..."

# 1. Wait for PostgreSQL
echo "⏳ Esperando PostgreSQL..."
while ! pg_isready -h $DB_HOST -p $DB_PORT; do
  sleep 1
done
echo "✅ PostgreSQL está disponible"

# 2. Run Migrations
echo "🔄 Ejecutando migraciones de base de datos..."
alembic upgrade head
echo "✅ Migraciones completadas exitosamente"

# 3. Start Application
echo "🎯 Iniciando aplicación FastAPI en puerto $PORT..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Comportamiento en Deploy:

1. **Render detecta push** → Trigger build
2. **Docker build** → Crea imagen
3. **Container start** → Ejecuta `entrypoint.sh`
4. **Wait for DB** → Verifica conectividad
5. **Run migrations** → `alembic upgrade head`
   - ✅ **Si éxito**: Continuar a paso 6
   - ❌ **Si falla**: Deploy se detiene, container no inicia
6. **Start app** → FastAPI disponible

---

## Justificación

**¿Por qué automático?**
- ✅ Zero intervención manual
- ✅ Deploy atómico (schema + código sincronizados)
- ✅ Rollback simple (redeploy commit anterior)
- ✅ Fail-safe: app no inicia si migración falla

**¿Por qué en entrypoint.sh?**
- Integración nativa con Docker
- Sin dependencias de CI/CD externo
- Portable a cualquier plataforma

**¿Por qué NOT separate pipeline?**
- Complejidad innecesaria para MVP
- Mayor time-to-deploy
- Dos puntos de fallo vs uno

---

## Consecuencias

### Positivas
- ✅ Deployment totalmente automatizado
- ✅ Seguridad: app no inicia con schema incorrecto
- ✅ Logs claros de éxito/fallo de migrations
- ✅ Consistencia: mismo proceso dev/prod

### Negativas
- ⚠️ Downtime durante migraciones (si son lentas)
- ⚠️ Migraciones destructivas sin rollback automático
- ⚠️ Sin backups automáticos (plan Free de Render)

### Mitigaciones
- **Downtime**: Migraciones deben ser no-bloqueantes (expand-contract pattern)
- **Destructivas**: Testing local obligatorio, revisión de código estricta
- **Backups**: Plan upgrade ($7/mes) o backups manuales antes de deploys críticos

---

## Restricciones de Migraciones

Para garantizar zero-downtime:

1. **NUNCA** eliminar columnas directamente
   - ✅ Usar expand-contract: agregar nueva → migrar datos → eliminar vieja
2. **NUNCA** renombrar tablas en una migración
   - ✅ Dividir en: crear nueva → copiar datos → eliminar vieja
3. **SIEMPRE** hacer cambios de schema backward-compatible
   - ✅ Agregar columnas como `nullable=True`
   - ✅ Usar defaults para columnas NOT NULL nuevas

---

## Validación en Cada Deploy

Verificar en logs de Render:
- [ ] `⏳ Esperando PostgreSQL...`
- [ ] `✅ PostgreSQL está disponible`
- [ ] `🔄 Ejecutando migraciones de base de datos...`
- [ ] `✅ Migraciones completadas exitosamente`
- [ ] `🎯 Iniciando aplicación FastAPI...`

Si falta cualquiera → **Deploy falló**

---

## Rollback de Migraciones

**Si migración causa problemas en producción**:

**Opción 1: Revert commit + push**
```bash
git revert HEAD
git push origin develop
# Auto-deploy ejecuta migración inversa (downgrade)
```

**Opción 2: Downgrade manual** (Shell de Render)
```bash
alembic downgrade -1
# Redeploy commit anterior
```

**Opción 3: Rollback a versión específica**
```bash
alembic downgrade <revision_id>
```

---

## Referencias

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Expand-Contract Pattern](https://www.martinfowler.com/bliki/ParallelChange.html)
- [ADR-016: Render Deployment Strategy](./ADR-016-render-deployment-strategy.md)
- `entrypoint.sh` - Implementación actual
