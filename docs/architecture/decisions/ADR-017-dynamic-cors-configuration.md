# ADR-017: Dynamic CORS Configuration Based on Environment

**Estado**: ✅ Aceptado
**Fecha**: 11 Nov 2025

---

## Contexto

Backend API necesita permitir requests desde frontend, pero los orígenes difieren entre entornos:
- **Desarrollo**: `http://localhost:5173` (Vite dev server)
- **Producción**: `https://www.rydercupfriends.com` (dominio custom)

**Problema**: CORS hardcodeado requiere cambios manuales en código al deployar.

**Alternativas**:
1. **CORS Permisivo** (`allow_origins=["*"]`): Inseguro en producción
2. **Config Files Separados**: Duplicación, propenso a errores
3. **Environment Variables**: Configuración dinámica desde deployment
4. **Reverse Proxy**: Complejidad innecesaria para MVP

---

## Decisión

**Configurar CORS dinámicamente desde variables de entorno** con lógica según `ENVIRONMENT`.

### Implementación (`main.py:100-130`):

```python
# Leer orígenes desde variable de entorno
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "")
allowed_origins = [origin.strip() for origin in FRONTEND_ORIGINS.split(",")]

# Incluir localhost SOLO en desarrollo
ENV = os.getenv("ENVIRONMENT", "development").lower()
if ENV != "production":
    allowed_origins.extend([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

# Fallback seguro si no hay orígenes configurados
if not allowed_origins:
    allowed_origins = ["http://localhost:5173"]

print(f"🔒 CORS allowed_origins: {allowed_origins}")
```

### Variables de Entorno:

**Desarrollo** (local):
```bash
ENVIRONMENT=development
# No requiere FRONTEND_ORIGINS (localhost se agrega automáticamente)
```

**Producción** (Render):
```bash
ENVIRONMENT=production
FRONTEND_ORIGINS=https://www.rydercupfriends.com
```

---

## Justificación

**¿Por qué dinámico?**
- ✅ Zero cambios en código entre dev/prod
- ✅ Seguridad mejorada (prod no permite localhost)
- ✅ Fácil agregar múltiples orígenes (CSV)
- ✅ Visible en logs (`🔒 CORS allowed_origins: [...]`)

**¿Por qué variable `ENVIRONMENT`?**
- Controla múltiples comportamientos (no solo CORS)
- Convención estándar en ecosistema Python
- Fail-safe: default a `development` (más permisivo para devs)

**¿Por qué NOT `*` en desarrollo?**
- Credentials (`allow_credentials=True`) incompatible con `*`
- Mantiene consistencia dev/prod

---

## Consecuencias

### Positivas
- ✅ Deployment sin cambios en código
- ✅ Seguridad mejorada (localhost bloqueado en prod)
- ✅ Debugging fácil (orígenes visibles en logs)
- ✅ Extensible (agregar staging u otros frontends)

### Negativas
- ⚠️ Variable mal configurada → CORS errors en producción
- ⚠️ Logs exponen configuración (no es sensible, pero visible)

### Mitigaciones
- Documentación clara en `CLAUDE.md` y `RENDER_DEPLOYMENT.md`
- Logs obligatorios en startup (`print(f"🔒 CORS...")`)
- Validación en troubleshooting checklist

---

## Validación

Verificar en cada deploy:
- [ ] Logs muestran `🔒 CORS allowed_origins: [...]`
- [ ] Frontend puede hacer login/register sin CORS errors
- [ ] Producción NO incluye localhost en allowed_origins

---

## Referencias

- [FastAPI CORS Docs](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [ADR-016: Render Deployment Strategy](./ADR-016-render-deployment-strategy.md)
- `main.py:100-130` - Implementación actual
