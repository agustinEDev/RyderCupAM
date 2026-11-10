# Pendientes de release

Lo que una release deja dicho para otra. Se borra la línea al hacerlo.

## 2.58.0

- **Quitar `GET /api/v1/auth/validate-reset-token/{token}`** (obsoleto desde la 2.57.0,
  ADR-048): el front ya valida por `POST /auth/validate-reset-token`. Quitar con él el
  tachado del token en `src/config/sentry_config.py` (`_tacha_el_token_del_enlace`) y
  comprobar que `oasdiff` lo da como cambio esperado.
- **Repetir en una migración la anulación de los enlaces en claro** (ADR-048, B-3): durante
  el despliegue escalonado de la 2.57.0 la 2.56 pudo escribir alguno después de la
  migración `b7e9d1f3a5c8`. Los mismos dos `UPDATE`:
  `verification_token = NULL WHERE verification_token !~ '^[0-9a-f]{64}$'` y
  `password_reset_token = NULL, reset_token_expires_at = NULL WHERE password_reset_token
  !~ '^[0-9a-f]{64}$'`.
- **Quitar los tokens del cuerpo** de las respuestas de login, registro, Google y refresco, y
  dejar de aceptar `Authorization: Bearer` (F-03). Antes tiene que estar en producción el
  front que ya no los lee (`ApiAuthRepository.js`).
- **`code_verifier` obligatorio** en el canje de Google (login y vincular), cuando el front ya
  lo envíe (FE-02).
