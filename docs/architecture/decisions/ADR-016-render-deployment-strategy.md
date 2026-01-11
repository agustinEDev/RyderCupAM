# ADR-016: Render.com Deployment Strategy

**Status**: ✅ Accepted
**Date**: Nov 11, 2025

---

## Context

We need production hosting for backend API (FastAPI + PostgreSQL) and frontend (React SPA) with:
- Automated deploy from Git
- Managed PostgreSQL database
- Free SSL/HTTPS
- Low cost for MVP

**Evaluated alternatives**:
1. **Heroku**: $7/month minimum (eliminated Free plan)
2. **AWS EC2/RDS**: High operational complexity, variable cost
3. **DigitalOcean**: Manual infrastructure management
4. **Railway**: Similar to Render but less mature
5. **Render.com**: Free plan available, native Docker

---

## Decision

**Use Render.com with auto-deploy from `develop` branch**

### Implemented Configuration:

**Backend** (Web Service):
- Runtime: Docker
- Branch: `develop`
- Region: Frankfurt (eu-central)
- Auto-deploy: Enabled
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

## Justification

**Why Render.com?**
- ✅ Free plan available (750h/month runtime)
- ✅ Native Docker (existing Dockerfile reusable)
- ✅ Managed PostgreSQL included
- ✅ Git auto-deploy out-of-the-box
- ✅ Free SSL/HTTPS (Let's Encrypt)
- ✅ EU region (Frankfurt) available - GDPR compliance

**Why `develop` branch?**
- Mandatory local testing before push
- Simple CI/CD without complex configuration
- Appropriate for MVP with small team

---

## Consequences

### Positive
- ✅ Automated deployment (git push → production in 3-5 min)
- ✅ Zero initial config (Dockerfile + entrypoint.sh sufficient)
- ✅ Automatic DB migrations on each deploy
- ✅ Centralized logs in dashboard
- ✅ $0 cost for MVP

### Negative
- ⚠️ Cold starts after 15 min inactivity (30-60s first request)
- ⚠️ No staging environment (develop = prod)
- ⚠️ Limited storage (1GB PostgreSQL)
- ⚠️ Single vendor dependency

### Mitigations
- **Cold starts**: Acceptable for MVP, upgrade to Starter ($7/month) if critical
- **No staging**: Local testing + strict code review
- **Storage**: 1GB sufficient for MVP (<1000 estimated users)
- **Vendor lock**: Portable Dockerfile, easy to migrate to another provider

---

## Migration Criteria

Consider migration when:
- Cold starts critically impact UX (>10 complaints/week)
- DB storage exceeds 800MB (80% limit)
- Need for real staging environment
- Compliance requirements not covered by Render

---

## References

- [Render Docs](https://render.com/docs)
- [RENDER_DEPLOYMENT.md](../../RENDER_DEPLOYMENT.md) - Complete guide
- [ADR-017: Dynamic CORS Configuration](./ADR-017-dynamic-cors-configuration.md)
- [ADR-018: Automated Database Migrations](./ADR-018-automated-database-migrations.md)
