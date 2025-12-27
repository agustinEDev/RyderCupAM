# ADR-024: Password Reset System con Security Best Practices

**Fecha**: 26 de diciembre de 2025
**Estado**: Aceptado
**Decisores**: Equipo de desarrollo

## Contexto y Problema

El sistema necesita un mecanismo seguro de recuperación de contraseña que minimice riesgos de enumeración de usuarios, timing attacks, token hijacking, secuestro de sesiones y ataques de fuerza bruta. Debe cumplir con OWASP ASVS V2.1 y mitigar las categorías A01, A02, A04, A07, A09 del OWASP Top 10.

## Opciones Consideradas

1. **Email con link temporal + validación básica**: Simple pero vulnerable
2. **Email con código de 6 dígitos**: Similar a 2FA, menos seguro para password reset
3. **Token criptográfico + security best practices**: Implementación completa con todas las mitigaciones
4. **Magic links sin password**: Cambio de paradigma (no aceptable)

## Decisión

**Adoptamos Token Criptográfico de 256 bits con Security Best Practices Completas** (Opción 3):

```
Flow:
├── POST /forgot-password → Token 256-bit + Email bilingüe (timing attack prevention)
├── GET /validate-reset-token/:token → Pre-validación (opcional, mejor UX)
└── POST /reset-password → Cambio + invalidación token + revocación sesiones
```

### Arquitectura (Clean Architecture):

- **Domain**: 3 métodos User entity + 2 eventos (PasswordResetRequested/Completed)
- **Application**: 3 Use Cases + 6 DTOs
- **Infrastructure**: Migration (2 campos + 2 índices) + Email templates bilingües
- **API**: 3 endpoints REST + rate limiting 3/h

## Justificación

### Security Features:

1. **Anti-Enumeración (A01)**: Mensaje genérico + delay artificial 200-400ms
2. **Token Seguro (A02)**: 256 bits `secrets.token_urlsafe(32)` + expiración 24h + uso único
3. **Session Invalidation (A01/A07)**: Revocación automática de TODOS los refresh tokens
4. **Password Policy (A07)**: OWASP ASVS V2.1 (12+ chars + complejidad)
5. **Rate Limiting (A04)**: 3 intentos/hora por email/IP (SlowAPI)
6. **Security Logging (A09)**: Audit trail completo con contexto HTTP

### Ventajas:
- ✅ Compliance OWASP Top 10 (6 categorías)
- ✅ Defense in depth (múltiples capas)
- ✅ Clean Architecture completa (testabilidad)
- ✅ Email bilingüe profesional (ES/EN)

## Consecuencias

### Positivas:
- ✅ Security hardening completo (A01, A02, A03, A04, A07, A09)
- ✅ 905 tests totales (+51 nuevos de password reset, 100% passing)
- ✅ Email templates reutilizables

### Negativas:
- ❌ Timing attack prevention añade latency (200-400ms)
- ❌ Requiere coordinación con frontend

### Riesgos Mitigados:
- **Token hijacking**: Expiración 24h + uso único
- **Brute force**: Rate limiting 3/h
- **User enumeration**: Mensaje genérico + delay artificial
- **Session hijacking**: Revocación automática de refresh tokens

## Validación

La decisión se considera exitosa si:
- [x] Tests unitarios completos (51/51 pasando - 100%)
- [x] Security features implementadas (6/6 completas)
- [x] Clean Architecture respetada (4 capas)
- [x] Email templates bilingües funcionando
- [x] Rate limiting configurado (3/hora)

## Referencias

- [OWASP ASVS V2.1](https://owasp.org/www-project-application-security-verification-standard/)
- [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
- [Python secrets module](https://docs.python.org/3/library/secrets.html)

## Notas de Implementación

### Implementado (26 Dic 2025):
- ✅ 11 archivos nuevos (domain events, use cases, tests, migration)
- ✅ 18 archivos modificados (entity, DTOs, repository, email service, routes)
- ✅ Total: ~1,200 líneas de código

### Lecciones Aprendidas:
- **Timing Attack Prevention**: Hash del email como seed para delay variable
- **Domain Events**: Capturar IP/User-Agent en el dominio para audit trail
- **Token Invalidation**: `token = None` + `expires_at = None` previene reutilización
- **Email Templates**: Reutilizar estructura de `verify_email` para consistencia
