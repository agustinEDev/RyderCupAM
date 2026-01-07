# ADR-027: Account Lockout - Brute Force Protection

**Fecha**: 7 de enero de 2026
**Estado**: Aceptado
**Decisores**: Equipo de desarrollo

## Contexto y Problema

El sistema necesita protección contra ataques de fuerza bruta en el login. Debe cumplir con OWASP A07 (Authentication Failures) sin afectar usabilidad de usuarios legítimos.

## Opciones Consideradas

1. **CAPTCHA después de N intentos**: Fricción, accesibilidad
2. **Solo Rate Limiting por IP**: Bypasseable con proxies
3. **Account Lockout permanente**: DoS risk, mala UX
4. **Account Lockout temporal + auto-desbloqueo**: Balance seguridad-usabilidad

## Decisión

**Adoptamos Account Lockout Temporal con Auto-Desbloqueo** (Opción 4):

```
Flow:
├── Intentos 1-9: HTTP 401 (registro de fallos)
├── Intento 10: HTTP 423 Locked (bloqueo 30 min)
├── Durante bloqueo: HTTP 423 incluso con password correcta
└── Tras 30 min: Auto-desbloqueo + reset contador en login exitoso
```

### Parámetros:
- `MAX_FAILED_ATTEMPTS = 10`
- `LOCKOUT_DURATION_MINUTES = 30`

### Arquitectura:
- **Domain**: 4 métodos User entity + 2 eventos (AccountLocked/Unlocked)
- **Application**: Login modificado + UnlockAccountUseCase + 2 DTOs
- **Infrastructure**: Migration (2 campos + índice)
- **API**: POST /unlock-account (pendiente rol Admin v2.1.0)

## Justificación

### Security Features:
1. **Brute Force Prevention (A07)**: 10 intentos máximos
2. **Auto-Recovery**: Desbloqueo tras 30 min (no requiere admin)
3. **Persistence**: Estado en BD (no memoria)
4. **Dual Check**: Pre-password + post-password verification
5. **HTTP 423**: Semánticamente correcto para lockout

### Decisiones Técnicas:

**Integración en User Entity** (vs LoginAttempt separado):
- Cohesión: Estado pertenece al User
- Performance: 1 query vs JOIN

**Naive Datetimes** (vs timezone-aware):
- Consistencia con codebase (85% usa naive)
- Migración global pendiente v1.14.0

**Dual Check Pattern**:
```python
# Pre-check
if user.is_locked(): raise AccountLockedException

# Post-check (tras record_failed_login)
if user.is_locked(): raise AccountLockedException  # Intento 10
```

## Consecuencias

### Positivas:
- ✅ Mitigación efectiva fuerza bruta (A07)
- ✅ 5/5 tests integración pasando
- ✅ Compatible con rate limiting (defensa en profundidad)
- ✅ Mínimo impacto usuarios legítimos

### Negativas:
- ❌ Posible DoS (atacante bloquea cuentas)
- ❌ Timezone naive (trade-off temporal)

### Riesgos Mitigados:
- Credential stuffing, dictionary attacks, automated brute force

## Validación

- [x] Tests completos (5/5 passing - 100%)
- [x] HTTP 423 al alcanzar 10 intentos
- [x] Auto-desbloqueo funcional
- [x] Counter reset tras login exitoso
- [x] Persistencia BD verificada

## Referencias

- [OWASP A07:2021](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/)
- [OWASP Auth Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#account-lockout)

## Notas de Implementación

### Implementado (7 Ene 2026):
- ✅ 3 commits (domain/app/infra + API/tests + fixes)
- ✅ 2 Domain Events + 1 excepción
- ✅ 1 migración BD + 5 tests integración

### Lecciones Aprendidas:
- **Dual Check**: Evita retornar 401 cuando debe ser 423 en intento 10
- **Test Strategy**: `X-Test-Client-ID` header bypassa rate limiting sin modificar producción
- **Timezone Trade-off**: Consistencia > safety (refactor global pendiente)
