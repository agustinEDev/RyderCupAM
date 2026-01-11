# ADR-017: Dynamic CORS Configuration Based on Environment

**Status**: ✅ Accepted
**Date**: Nov 11, 2025

---

## Context

Backend API needs to allow requests from frontend, but origins differ between environments:
- **Development**: `http://localhost:5173` (Vite dev server)
- **Production**: `https://www.rydercupfriends.com` (custom domain)

**Problem**: Hardcoded CORS requires manual code changes when deploying.

**Alternatives**:
1. **Permissive CORS** (`allow_origins=["*"]`): Insecure in production
2. **Separate Config Files**: Duplication, error-prone
3. **Environment Variables**: Dynamic configuration from deployment
4. **Reverse Proxy**: Unnecessary complexity for MVP

---

## Decision

**Configure CORS dynamically from environment variables** with logic based on `ENVIRONMENT`.

### Implementation (`main.py:100-130`):

```python
# Read origins from environment variable
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "")
allowed_origins = [origin.strip() for origin in FRONTEND_ORIGINS.split(",")]

# Include localhost ONLY in development
ENV = os.getenv("ENVIRONMENT", "development").lower()
if ENV != "production":
    allowed_origins.extend([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

# Secure fallback if no origins configured
if not allowed_origins:
    allowed_origins = ["http://localhost:5173"]

print(f"🔒 CORS allowed_origins: {allowed_origins}")
```

### Environment Variables:

**Development** (local):
```bash
ENVIRONMENT=development
# No FRONTEND_ORIGINS required (localhost added automatically)
```

**Production** (Render):
```bash
ENVIRONMENT=production
FRONTEND_ORIGINS=https://www.rydercupfriends.com
```

---

## Justification

**Why dynamic?**
- ✅ Zero code changes between dev/prod
- ✅ Improved security (prod doesn't allow localhost)
- ✅ Easy to add multiple origins (CSV)
- ✅ Visible in logs (`🔒 CORS allowed_origins: [...]`)

**Why `ENVIRONMENT` variable?**
- Controls multiple behaviors (not just CORS)
- Standard convention in Python ecosystem
- Fail-safe: defaults to `development` (more permissive for devs)

**Why NOT `*` in development?**
- Credentials (`allow_credentials=True`) incompatible with `*`
- Maintains dev/prod consistency

---

## Consequences

### Positive
- ✅ Deployment without code changes
- ✅ Improved security (localhost blocked in prod)
- ✅ Easy debugging (origins visible in logs)
- ✅ Extensible (add staging or other frontends)

### Negative
- ⚠️ Misconfigured variable → CORS errors in production
- ⚠️ Logs expose configuration (not sensitive, but visible)

### Mitigations
- Clear documentation in `CLAUDE.md` and `RENDER_DEPLOYMENT.md`
- Mandatory startup logs (`print(f"🔒 CORS...")`)
- Validation in troubleshooting checklist

---

## Validation

Verify on each deploy:
- [ ] Logs show `🔒 CORS allowed_origins: [...]`
- [ ] Frontend can login/register without CORS errors
- [ ] Production does NOT include localhost in allowed_origins

---

## References

- [FastAPI CORS Docs](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [ADR-016: Render Deployment Strategy](./ADR-016-render-deployment-strategy.md)
- `main.py:100-130` - Current implementation
