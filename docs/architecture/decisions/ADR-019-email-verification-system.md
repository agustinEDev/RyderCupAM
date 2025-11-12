# ADR-019: Email Verification System

**Estado**: ✅ Aceptado
**Fecha**: 12 Nov 2025

---

## Contexto

Necesitamos verificar que los emails de los usuarios son reales y pertenecen a quien se registra.

**Requisitos**:
- Validar propiedad del email
- Prevenir spam y cuentas falsas
- Bajo friction en UX (no obligatorio para usar app)
- Testeable sin enviar emails reales
- Soporte multiidioma (ES/EN)

---

## Decisión

**Sistema de verificación por email con tokens UUID únicos persistidos** + **Mailgun como proveedor**.

### Arquitectura

**Domain Layer**:
- `User.generate_verification_token()`: Genera UUID4
- `User.verify_email()`: Marca verificado, emite `EmailVerifiedEvent`
- Campos: `email_verified: bool`, `verification_token: Optional[str]`

**Application Layer**:
- `RegisterUserUseCase`: Genera token, envía email en registro
- `VerifyEmailUseCase`: Valida token, marca usuario como verificado

**Infrastructure Layer**:
- `EmailService`: Implementación Mailgun API
- `UserRepository.find_by_verification_token()`: Búsqueda por token
- Endpoint: `POST /api/v1/auth/verify-email`

**Flujo**:
1. Registro → genera token UUID → envía email bilingüe
2. Usuario click link → frontend extrae token
3. `POST /auth/verify-email` → valida token → marca verificado
4. Emite `EmailVerifiedEvent` para auditoría

---

## Alternativas Rechazadas

**1. JWT Firmados como Tokens**
- ❌ No revocables sin blacklist adicional
- ✅ **Elegido**: UUID en DB (revocable, testeable)

**2. SendGrid / AWS SES**
- ❌ SendGrid: Más caro ($15/mes vs gratis)
- ❌ AWS SES: Requiere verificación de dominio previa
- ✅ **Elegido**: Mailgun (12k emails/mes gratis, API simple)

**3. Verificación Obligatoria (Bloquea Login)**
- ❌ Alta fricción UX (usuarios sin acceso inmediato)
- ✅ **Elegido**: Opcional (pueden usar app, features limitadas sin verificar)

**4. Magic Links (Sin Password)**
- ❌ Cambia paradigma completo de autenticación
- ✅ **Elegido**: Email verification separado de auth

---

## Consecuencias

### Positivas
✅ **Seguridad**: Solo quien controla el email puede verificar
✅ **Revocable**: Token en DB, eliminable si necesario
✅ **Testeable**: Mock email service en tests
✅ **Clean Architecture**: EmailService en infrastructure
✅ **UX Flexible**: No bloquea uso de app
✅ **Bilingüe**: ES/EN desde inicio
✅ **Auditable**: `EmailVerifiedEvent` registra verificaciones

### Negativas
⚠️ **Cuentas No Verificadas**: Usuarios pueden usar app sin verificar
⚠️ **Tokens Sin Expirar**: Implementación actual no expira tokens
⚠️ **Sin Reenvío**: No hay endpoint para reenviar email
⚠️ **Dependencia Externa**: Requiere Mailgun disponible

**Mitigaciones**:
- Limitar features premium a usuarios verificados
- Fase 2: Expiración (7 días) y reenvío de emails

---

## Configuración

### Variables de Entorno
```env
MAILGUN_API_KEY=...
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL=noreply@rydercupfriends.com
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
FRONTEND_URL=http://localhost:5173  # Vite default port
```

### Migración de Base de Datos
```sql
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN verification_token VARCHAR(255) NULL;
CREATE INDEX idx_verification_token ON users(verification_token);
```

---

## Integración Frontend

**Componentes Nuevos**:
- `VerifyEmailPage` (`src/pages/VerifyEmail.jsx`): Página de destino del enlace de verificación
- `EmailVerificationBanner` (`src/components/EmailVerificationBanner.jsx`): Warning para usuarios no verificados

**Timing UX Optimizado**:
- 1.5s spinner después de verificación exitosa (feedback visual)
- 3s mensaje de confirmación antes de redirect (tiempo de lectura)
- Prevención de ejecución doble (React Strict Mode guard)
- Actualización automática de localStorage

**Estados Manejados**:
- `verifying`: Spinner visible durante llamada API
- `success`: Email verificado → auto-redirect a dashboard
- `error`: Token inválido/expirado → botones de navegación
- `invalid`: Token missing → mensaje de error

**Indicadores Visuales**:
- Dashboard: Banner amarillo si `email_verified === false`
- Profile: Badge verde/amarillo según estado de verificación
- Login: Log en consola si `email_verification_required === true`

**Referencias**: Ver `RyderCupWeb/CLAUDE.md` para detalles completos de implementación frontend.

---

## Métricas

**Backend**:
- **Archivos nuevos**: 3 (EmailService, VerifyEmailUseCase, EmailVerifiedEvent)
- **Archivos modificados**: 8 (User entity, DTOs, repositories, routes, mappers)
- **Tests añadidos**: 15+ (unit + integration)
- **Endpoints**: +1 (`POST /auth/verify-email`)
- **Domain Events**: +1 (`EmailVerifiedEvent`)

**Frontend**:
- **Componentes nuevos**: 2 (VerifyEmailPage, EmailVerificationBanner)
- **Páginas modificadas**: 4 (App, Dashboard, Login, Profile, EditProfile)
- **Rutas añadidas**: 1 (`/verify-email`)

---

## Referencias

- [ADR-007: Domain Events Pattern](./ADR-007-domain-events-pattern.md)
- [ADR-013: External Services Pattern](./ADR-013-external-services-pattern.md)
- [Mailgun API Documentation](https://documentation.mailgun.com/en/latest/api-sending.html)
