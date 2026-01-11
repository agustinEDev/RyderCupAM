# ADR-018: Automated Database Migrations in Production

**Status**: ✅ Accepted
**Date**: Nov 11, 2025

---

## Context

We need to synchronize database schema with code on each production deployment.

**Problem**: Manual migrations are error-prone and require human intervention in deploys.

**Alternatives**:
1. **Manual Migrations**: Run `alembic upgrade head` manually via SSH/Shell
2. **Separate CD Pipeline**: Migrations as independent step before deploy
3. **Automated in Entrypoint**: Migrations executed automatically when starting app
4. **Blue-Green Deployment**: Migrations in pre-deploy hook

---

## Decision

**Execute migrations automatically in `entrypoint.sh` before starting the application.**

### Implementation

**entrypoint.sh flow**:
1. Wait for PostgreSQL (pg_isready)
2. Run migrations (alembic upgrade head)
3. Start application (uvicorn main:app)

**Deployment Behavior**:
1. Render detects push → Trigger build
2. Docker build → Create image
3. Container start → Execute entrypoint.sh
4. Wait for DB → Verify connectivity
5. Run migrations → Success continues / Failure stops deploy
6. Start app → FastAPI available

---

## Justification

**Why automatic?**
- ✅ Zero manual intervention
- ✅ Atomic deploy (schema + code synchronized)
- ✅ Simple rollback (redeploy previous commit)
- ✅ Fail-safe: app doesn't start if migration fails

**Why in entrypoint.sh?**
- Native Docker integration
- No external CI/CD dependencies
- Portable to any platform

---

## Consequences

### Positive
- ✅ Fully automated deployment
- ✅ Security: app doesn't start with incorrect schema
- ✅ Clear logs of migration success/failure
- ✅ Consistency: same process dev/prod

### Negative
- ⚠️ Downtime during migrations (if slow)
- ⚠️ Destructive migrations without automatic rollback
- ⚠️ No automatic backups (Render Free plan)

### Mitigations
- **Downtime**: Use expand-contract pattern (non-blocking migrations)
- **Destructive**: Mandatory local testing, strict code review
- **Backups**: Plan upgrade or manual backups before critical deploys

---

## Migration Restrictions

**To ensure zero-downtime:**

1. NEVER delete columns directly → Use expand-contract (add new → migrate → delete old)
2. NEVER rename tables in one migration → Split into: create new → copy data → delete old
3. ALWAYS make schema changes backward-compatible → Add columns as nullable, use defaults for NOT NULL

---

## Validation on Each Deploy

Verify in Render logs:
- [ ] ⏳ Waiting for PostgreSQL...
- [ ] ✅ PostgreSQL is available
- [ ] 🔄 Running database migrations...
- [ ] ✅ Migrations completed successfully
- [ ] 🎯 Starting FastAPI application...

---

## Migration Rollback

**If migration causes problems:**

**Option 1: Revert commit + push** → Auto-deploy executes inverse migration
**Option 2: Manual downgrade** (Render Shell) → `alembic downgrade -1` + redeploy
**Option 3: Rollback to specific version** → `alembic downgrade <revision_id>`

---

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Expand-Contract Pattern](https://www.martinfowler.com/bliki/ParallelChange.html)
- [ADR-016: Render Deployment Strategy](./ADR-016-render-deployment-strategy.md)
- `entrypoint.sh` - Current implementation
