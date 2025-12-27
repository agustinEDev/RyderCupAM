# 🔑 Password Reset System - Frontend Integration Guide

> **Versión Backend:** v1.11.0
> **Fecha:** 26 de Diciembre de 2025
> **Endpoints:** 3 REST endpoints con autenticación pública

---

## 📋 Resumen Ejecutivo

El backend provee un sistema completo de recuperación de contraseña con 3 endpoints REST:

1. **Solicitar reset** (`POST /forgot-password`) - Envía email con token
2. **Validar token** (`GET /validate-reset-token/:token`) - Pre-validación opcional (mejor UX)
3. **Completar reset** (`POST /reset-password`) - Cambia contraseña + revoca sesiones

**Security Features:**
- Token 256-bit seguro con expiración 24h
- Rate limiting 3 intentos/hora
- Email bilingüe (ES/EN)
- Invalidación automática de todas las sesiones activas
- Timing attack prevention (backend)

---

## 🌐 API Endpoints

### Base URL
```
Development: http://localhost:8000/api/v1/auth
Production: https://rydercupam.onrender.com/api/v1/auth
```

---

## 1️⃣ Solicitar Reset de Contraseña

### Endpoint
```http
POST /api/v1/auth/forgot-password
Content-Type: application/json
```

### Request Body
```json
{
  "email": "user@example.com"
}
```

### Response (200 OK - SIEMPRE)
```json
{
  "message": "Si el email existe, se ha enviado un enlace de recuperación. Revisa tu bandeja de entrada."
}
```

**⚠️ IMPORTANTE:**
- El endpoint SIEMPRE retorna 200 OK con el mismo mensaje, exista o no el email (anti-enumeración de usuarios)
- El email puede tardar hasta 1-2 minutos en llegar (Mailgun queue)
- Rate limit: 3 intentos/hora por email

### Response (429 Too Many Requests)
```json
{
  "detail": "Rate limit exceeded. Try again in 60 minutes."
}
```

### Response (422 Validation Error)
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "Invalid email format",
      "input": "invalid-email"
    }
  ]
}
```

### Email Template (Usuario recibe)
```
Subject: Recupera tu contraseña - Ryder Cup Friends

¡Hola!

Hemos recibido una solicitud para restablecer la contraseña de tu cuenta.

[Restablecer Contraseña]  ← Link: {FRONTEND_URL}/reset-password?token={TOKEN}

Este enlace expira en 24 horas.

⚠️ Si no solicitaste este cambio, ignora este email. Tu contraseña permanecerá sin cambios.

---
Ryder Cup Friends Team
```

---

## 2️⃣ Validar Token (Opcional - Mejor UX)

### Endpoint
```http
GET /api/v1/auth/validate-reset-token/{token}
```

### URL Params
- `token` (string, required): Token recibido por email

### Response (200 OK - Token válido)
```json
{
  "valid": true,
  "message": "Token válido. Puedes proceder a cambiar tu contraseña."
}
```

### Response (400 Bad Request - Token inválido/expirado)
```json
{
  "detail": "Invalid or expired password reset token"
}
```

### Uso Recomendado
```typescript
// Al cargar la página /reset-password?token=xxx
async function validateTokenOnLoad(token: string) {
  try {
    const response = await fetch(`${API_URL}/validate-reset-token/${token}`);

    if (response.ok) {
      // Mostrar formulario de nueva contraseña
      showPasswordForm();
    } else {
      // Mostrar mensaje de token inválido/expirado
      showError('El enlace es inválido o ha expirado. Solicita uno nuevo.');
      redirectToForgotPassword();
    }
  } catch (error) {
    showError('Error al validar el token. Intenta nuevamente.');
  }
}
```

---

## 3️⃣ Completar Reset de Contraseña

### Endpoint
```http
POST /api/v1/auth/reset-password
Content-Type: application/json
```

### Request Body
```json
{
  "token": "abc123xyz...",
  "new_password": "MyNewSecurePass123!@"
}
```

### Password Requirements (OWASP ASVS V2.1)
- ✅ Mínimo 12 caracteres
- ✅ Al menos 1 mayúscula
- ✅ Al menos 1 minúscula
- ✅ Al menos 1 dígito
- ✅ Al menos 1 símbolo (!@#$%^&*()_+-=[]{}|;:,.<>?)
- ❌ No puede ser contraseña común (password, admin, qwerty, etc.)

### Response (200 OK - Reset exitoso)
```json
{
  "message": "Contraseña cambiada exitosamente. Todas tus sesiones activas han sido cerradas. Por favor, inicia sesión nuevamente."
}
```

**⚠️ IMPORTANTE:**
- Todas las sesiones activas (refresh tokens) son revocadas automáticamente
- El usuario debe hacer login nuevamente en TODOS sus dispositivos
- El token de reset se invalida y no puede reutilizarse

### Response (400 Bad Request - Token inválido/expirado)
```json
{
  "detail": "Invalid or expired password reset token"
}
```

### Response (400 Bad Request - Contraseña débil)
```json
{
  "detail": "Password does not meet security requirements: Password must be at least 12 characters long and include uppercase, lowercase, digit, and special character"
}
```

### Response (429 Too Many Requests)
```json
{
  "detail": "Rate limit exceeded. Try again in 60 minutes."
}
```

### Email de Confirmación (Usuario recibe)
```
Subject: Tu contraseña ha sido cambiada - Ryder Cup Friends

¡Hola!

Tu contraseña ha sido cambiada exitosamente.

Por seguridad, hemos cerrado todas tus sesiones activas. Inicia sesión nuevamente con tu nueva contraseña.

⚠️ Si no realizaste este cambio, contacta con soporte inmediatamente.

---
Ryder Cup Friends Team
```

---

## 🎨 Flujo de Usuario Recomendado (UX)

### Página 1: Forgot Password (`/forgot-password`)
```tsx
import { useState } from 'react';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        setSubmitted(true);
      } else if (response.status === 429) {
        alert('Demasiados intentos. Intenta en 1 hora.');
      } else {
        alert('Error al enviar email. Intenta nuevamente.');
      }
    } catch (error) {
      alert('Error de conexión. Intenta nuevamente.');
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <div>
        <h2>Email Enviado</h2>
        <p>
          Si el email existe en nuestro sistema, recibirás un enlace de recuperación.
          <br />
          Revisa tu bandeja de entrada (y spam).
        </p>
        <p className="text-sm text-gray-600">
          El enlace expira en 24 horas.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>¿Olvidaste tu contraseña?</h2>
      <p>Ingresa tu email y te enviaremos un enlace de recuperación.</p>

      <input
        type="email"
        placeholder="tu@email.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        disabled={loading}
      />

      <button type="submit" disabled={loading}>
        {loading ? 'Enviando...' : 'Enviar Enlace'}
      </button>

      <p className="rate-limit-notice">
        ⚠️ Límite: 3 intentos por hora
      </p>
    </form>
  );
}
```

### Página 2: Reset Password (`/reset-password?token=xxx`)
```tsx
import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const token = searchParams.get('token');
  const [validating, setValidating] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Pre-validar token al cargar
  useEffect(() => {
    if (!token) {
      navigate('/forgot-password');
      return;
    }

    async function validateToken() {
      try {
        const response = await fetch(`${API_URL}/validate-reset-token/${token}`);
        setTokenValid(response.ok);

        if (!response.ok) {
          setTimeout(() => navigate('/forgot-password'), 3000);
        }
      } catch {
        setTokenValid(false);
      } finally {
        setValidating(false);
      }
    }

    validateToken();
  }, [token, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Validación frontend
    if (newPassword !== confirmPassword) {
      alert('Las contraseñas no coinciden');
      return;
    }

    if (newPassword.length < 12) {
      alert('La contraseña debe tener al menos 12 caracteres');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      });

      if (response.ok) {
        setSuccess(true);
        setTimeout(() => navigate('/login'), 3000);
      } else if (response.status === 400) {
        const data = await response.json();
        alert(data.detail || 'Token inválido o contraseña débil');
      } else if (response.status === 429) {
        alert('Demasiados intentos. Intenta en 1 hora.');
      } else {
        alert('Error al cambiar contraseña. Intenta nuevamente.');
      }
    } catch (error) {
      alert('Error de conexión. Intenta nuevamente.');
    } finally {
      setLoading(false);
    }
  }

  if (validating) {
    return <div>Validando enlace...</div>;
  }

  if (!tokenValid) {
    return (
      <div>
        <h2>Enlace Inválido</h2>
        <p>El enlace es inválido o ha expirado.</p>
        <p>Serás redirigido para solicitar uno nuevo...</p>
      </div>
    );
  }

  if (success) {
    return (
      <div>
        <h2>✅ Contraseña Cambiada</h2>
        <p>Tu contraseña ha sido actualizada exitosamente.</p>
        <p>Todas tus sesiones activas han sido cerradas por seguridad.</p>
        <p>Redirigiendo al login...</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Nueva Contraseña</h2>

      <div>
        <label>Nueva contraseña</label>
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          disabled={loading}
          minLength={12}
        />
      </div>

      <div>
        <label>Confirmar contraseña</label>
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          disabled={loading}
          minLength={12}
        />
      </div>

      <div className="password-requirements">
        <p><strong>Requisitos:</strong></p>
        <ul>
          <li>Mínimo 12 caracteres</li>
          <li>Al menos 1 mayúscula</li>
          <li>Al menos 1 minúscula</li>
          <li>Al menos 1 número</li>
          <li>Al menos 1 símbolo (!@#$%...)</li>
        </ul>
      </div>

      <button type="submit" disabled={loading}>
        {loading ? 'Cambiando...' : 'Cambiar Contraseña'}
      </button>
    </form>
  );
}
```

---

## 🔐 Seguridad y Mejores Prácticas

### ✅ Implementado en Backend
1. **Anti-enumeración**: Mismo mensaje exista o no el email
2. **Timing attack prevention**: Delay artificial variable
3. **Rate limiting**: 3 intentos/hora por email/IP
4. **Token seguro**: 256 bits, expiración 24h, uso único
5. **Session invalidation**: Revoca todos los refresh tokens
6. **Security logging**: Audit trail completo

### ✅ Recomendaciones Frontend
1. **No asumir email existente**: Mostrar siempre mensaje genérico
2. **Pre-validar token**: Mejor UX, feedback inmediato
3. **Validación frontend**: Evitar requests innecesarios
4. **Mostrar requisitos**: Ayudar al usuario con password policy
5. **Manejar rate limiting**: Mostrar tiempo de espera
6. **Redirigir post-reset**: Enviar a login tras cambio exitoso

---

## 🧪 Testing de Integración

### Caso de Prueba 1: Flujo Exitoso
```bash
# 1. Solicitar reset
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'

# 2. Copiar token del email recibido

# 3. Validar token
curl http://localhost:8000/api/v1/auth/validate-reset-token/ABC123XYZ

# 4. Completar reset
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token":"ABC123XYZ","new_password":"MyNewPass123!@#"}'
```

### Caso de Prueba 2: Rate Limiting
```bash
# Intentar 4 veces en menos de 1 hora
for i in {1..4}; do
  curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com"}'
  echo "\nIntento $i"
done

# El 4to intento debería retornar 429
```

### Caso de Prueba 3: Token Expirado
```bash
# Esperar 24 horas o modificar backend temporalmente
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token":"EXPIRED_TOKEN","new_password":"MyNewPass123!@#"}'

# Debería retornar 400 con mensaje de token expirado
```

---

## 📞 Soporte y Troubleshooting

### Email no llega
- ✅ Verificar spam/junk folder
- ✅ Esperar hasta 2 minutos (Mailgun queue)
- ✅ Verificar que el email esté verificado en el sistema
- ✅ Revisar logs de backend: `logs/security_audit.log`

### Token inválido/expirado
- ✅ Solicitar nuevo token (el anterior se invalida)
- ✅ No reutilizar tokens ya usados
- ✅ Los tokens expiran en 24 horas exactas

### Rate limiting
- ✅ Esperar 60 minutos entre intentos
- ✅ El límite es por email Y por IP
- ✅ En desarrollo: reiniciar backend resetea límites

### Contraseña rechazada
- ✅ Verificar requisitos: 12+ chars, mayúscula, minúscula, número, símbolo
- ✅ No usar contraseñas comunes (password, admin, 123456, etc.)
- ✅ Validar frontend antes de enviar request

---

## 🔗 Referencias

- **CHANGELOG.md**: Detalles completos de v1.11.0
- **ADR-024**: Decisiones arquitectónicas de seguridad
- **OWASP Cheat Sheet**: https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html
- **Backend Source**: `/src/modules/user/application/use_cases/*password_reset*`
- **Email Templates**: `/src/shared/infrastructure/email/email_service.py` (líneas 200-350)

---

**Versión:** v1.11.0
**Última actualización:** 26 de Diciembre de 2025
**Mantenedor:** Backend Team - Ryder Cup Friends
