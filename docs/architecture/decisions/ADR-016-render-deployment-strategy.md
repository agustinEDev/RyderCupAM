# ADR-016: Render.com Deployment Strategy

**Estado**: ✅ Aceptado
**Fecha**: 11 Nov 2025

---

## Contexto

Necesitamos hosting en producción para backend API (FastAPI + PostgreSQL) y frontend (React SPA) con:
- Deploy automatizado desde Git
- Base de datos PostgreSQL gestionada
- SSL/HTTPS gratuito
- Costo bajo para MVP

**Alternativas evaluadas**:
1. **Heroku**: $7/mes mínimo (eliminó plan Free)
2. **AWS EC2/RDS**: Complejidad operativa alta, costo variable
3. **DigitalOcean**: Gestión manual de infraestructura
4. **Railway**: Similar a Render pero menos maduro
5. **Render.com**: Plan Free disponible, Docker nativo

---

## Decisión

**Usar Render.com con auto-deploy desde rama `develop`**

### Configuración Implementada:

**Backend** (Web Service):
- Runtime: Docker
- Branch: `develop`
- Region: Frankfurt (eu-central)
- Auto-deploy: Activado
- Entrypoint: `entrypoint.sh` (wait DB → migrations → start app)

**Frontend** (Static Site):
- Runtime: Static Site
- Build: `npm run build` → `dist/`
- Branch: `develop`
- Region: Frankfurt
- Rewrites: `/* → /index.html` (React Router SPA)

**Database** (PostgreSQL):
- Version: 15
- Plan: Free (1GB storage)
- Connection: Internal Database URL
- Region: Frankfurt

---

## Justificación

**¿Por qué Render.com?**
- ✅ Plan Free disponible (750h/mes runtime)
- ✅ Docker nativo (Dockerfile existente reutilizable)
- ✅ PostgreSQL gestionado incluido
- ✅ Auto-deploy desde Git out-of-the-box
- ✅ SSL/HTTPS gratuito (Let's Encrypt)
- ✅ Región EU (Frankfurt) disponible - RGPD compliance

**¿Por qué rama `develop`?**
- Testing local obligatorio antes de push
- CI/CD simple sin configuración compleja
- Apropiado para MVP con equipo pequeño

---

## Consecuencias

### Positivas
- ✅ Deployment automatizado (git push → producción en 3-5 min)
- ✅ Zero config inicial (Dockerfile + entrypoint.sh suficientes)
- ✅ Migraciones DB automáticas en cada deploy
- ✅ Logs centralizados en dashboard
- ✅ Costo $0 para MVP

### Negativas
- ⚠️ Cold starts tras 15 min inactividad (30-60s primera petición)
- ⚠️ Sin staging environment (develop = prod)
- ⚠️ Storage limitado (1GB PostgreSQL)
- ⚠️ Dependencia de vendor único

### Mitigaciones
- **Cold starts**: Acceptable para MVP, upgrade a Starter ($7/mes) si es crítico
- **No staging**: Testing local + revisión de código estricta
- **Storage**: 1GB suficiente para MVP (<1000 usuarios estimados)
- **Vendor lock**: Dockerfile portable, fácil migrar a otro proveedor

---

## Criterios de Migración

Considerar migración cuando:
- Cold starts impacten UX críticamente (>10 quejas/semana)
- Storage de BD supere 800MB (80% límite)
- Necesidad de staging environment real
- Requerimientos de compliance no cubiertos por Render

---

## Referencias

- [Render Docs](https://render.com/docs)
- [RENDER_DEPLOYMENT.md](../../RENDER_DEPLOYMENT.md) - Guía completa
- [ADR-017: Dynamic CORS Configuration](./ADR-017-dynamic-cors-configuration.md)
- [ADR-018: Automated Database Migrations](./ADR-018-automated-database-migrations.md)
