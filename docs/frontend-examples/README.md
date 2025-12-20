# 📦 Frontend Code Examples - Email Verification & Authentication

Esta carpeta contiene componentes y código de ejemplo listos para usar en el frontend de **RyderCupWeb**.

## 🔐 IMPORTANTE: Seguridad v1.8.0+

**El backend ahora usa httpOnly cookies para tokens JWT:**
- ✅ Los tokens se envían automáticamente desde cookies seguras
- ✅ NO es necesario usar `localStorage` (vulnerable a XSS)
- ✅ NO es necesario añadir headers `Authorization` manualmente
- ✅ Requiere `withCredentials: true` en Axios o `credentials: 'include'` en fetch

**Migración desde localStorage:**
```javascript
// ❌ ANTIGUO (v1.7.0) - Vulnerable a XSS
localStorage.setItem('access_token', token);
axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

// ✅ NUEVO (v1.8.0+) - Seguro con httpOnly
// No hay que hacer nada, el navegador gestiona las cookies automáticamente
const api = axios.create({
  withCredentials: true  // Solo esto es necesario
});
```

## 📁 Archivos Incluidos

### Componentes React

1. **VerifyEmailPage.jsx** + **VerifyEmailPage.css**
   - Página completa para verificar el email
   - Ruta: `/verify-email?token=ABC123`
   - Estados: verifying, success, error
   - Auto-redirect al login después de verificación exitosa

2. **VerificationEmailSent.jsx** + **VerificationEmailSent.css**
   - Componente para mostrar después del registro
   - Informa al usuario que debe revisar su email
   - Incluye botón para reenviar email (preparado para futuro)

### Servicios

3. **api.js**
   - Configuración completa de Axios con httpOnly cookies
   - Todos los endpoints del backend
   - `withCredentials: true` para enviar cookies automáticamente
   - ⚠️ NO usa localStorage (tokens en cookies httpOnly)
   - Helpers para autenticación asíncrona

## 🚀 Instalación Rápida

### 1. Copiar archivos al proyecto

```bash
# En tu proyecto de frontend (RyderCupWeb)
cd src

# Copiar componentes
cp /path/to/backend/docs/frontend-examples/VerifyEmailPage.* ./pages/
cp /path/to/backend/docs/frontend-examples/VerificationEmailSent.* ./components/

# Copiar servicio API
cp /path/to/backend/docs/frontend-examples/api.js ./services/
```

### 2. Instalar dependencias

```bash
npm install axios react-router-dom
# o
yarn add axios react-router-dom
```

### 3. Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto frontend:

```env
REACT_APP_API_URL=http://localhost:8000
```

En producción:
```env
REACT_APP_API_URL=https://api.rydercupfriends.com
```

⚠️ **IMPORTANTE para producción con httpOnly cookies:**
- El frontend y backend deben estar en el mismo dominio base
- Ejemplo válido: `app.rydercupfriends.com` → `api.rydercupfriends.com`
- El backend debe configurar CORS con `allow_credentials=True` y los orígenes específicos

### 4. Agregar rutas

En tu archivo de rutas (`App.jsx` o `router.jsx`):

```jsx
import { VerifyEmailPage } from './pages/VerifyEmailPage';

// En tus rutas:
<Route path="/verify-email" element={<VerifyEmailPage />} />
```

### 5. Actualizar página de registro

```jsx
import { VerificationEmailSent } from './components/VerificationEmailSent';
import { authApi } from './services/api';

const RegisterPage = () => {
  const [showVerification, setShowVerification] = useState(false);
  const [userEmail, setUserEmail] = useState('');

  const handleRegister = async (formData) => {
    try {
      const response = await authApi.register(formData);
      setUserEmail(response.data.email);
      setShowVerification(true);
      
      // ✅ NO necesitas guardar tokens - las cookies httpOnly se establecen automáticamente
      // ❌ NO HAGAS: localStorage.setItem('access_token', response.data.access_token)
      
    } catch (error) {
      // Manejar error
    }
  };

  if (showVerification) {
    return <VerificationEmailSent email={userEmail} />;
  }

  return <RegisterForm onSubmit={handleRegister} />;
};
```

### 6. Usar con fetch nativo (alternativa a Axios)

Si prefieres usar `fetch` en lugar de Axios:

```javascript
// Hacer login con fetch + httpOnly cookies
async function login(email, password) {
  const response = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include', // ✅ CRÍTICO: Envía y recibe cookies
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error('Login failed');
  }

  const data = await response.json();
  // Las cookies httpOnly se establecieron automáticamente
  return data.user;
}

// Hacer request autenticado
async function getCurrentUser() {
  const response = await fetch('http://localhost:8000/api/v1/auth/current-user', {
    credentials: 'include', // ✅ Envía las cookies automáticamente
  });

  if (!response.ok) {
    throw new Error('Not authenticated');
  }

  return response.json();
}

// Logout
async function logout() {
  await fetch('http://localhost:8000/api/v1/auth/logout', {
    method: 'POST',
    credentials: 'include', // ✅ Envía las cookies para invalidarlas
  });
  // El backend limpia las cookies automáticamente
}
```

## 🎨 Personalización

### Colores

Los componentes usan un gradiente púrpura por defecto. Para cambiar los colores:

**VerifyEmailPage.css:**
```css
/* Cambiar fondo del contenedor */
.verify-email-container {
  background: linear-gradient(135deg, #TU_COLOR_1 0%, #TU_COLOR_2 100%);
}

/* Cambiar color de spinner */
.spinner {
  border-top: 5px solid #TU_COLOR;
}
```

**VerificationEmailSent.css:**
```css
/* Cambiar gradiente del icono de email */
.email-icon {
  background: linear-gradient(135deg, #TU_COLOR_1 0%, #TU_COLOR_2 100%);
}
```

### Textos

Todos los textos están en español e inglés. Puedes modificarlos directamente en los archivos JSX.

### Estilos

Los componentes usan CSS vanilla para facilitar la integración. Puedes:
- Convertir a CSS Modules
- Migrar a Styled Components
- Adaptar a Tailwind CSS
- Usar tu sistema de diseño existente

## 📋 Flujo Completo

```
1. Usuario se registra
   └─> POST /api/v1/auth/register

2. Backend envía email
   └─> Mailgun envía email con link

3. Usuario hace clic en el link
   └─> Frontend: /verify-email?token=ABC123

4. Frontend llama al backend
   └─> POST /api/v1/auth/verify-email

5. Backend verifica y responde
   └─> {message, email_verified: true}

6. Frontend muestra éxito
   └─> Redirect a /login después de 3s
```

## 🧪 Testing

### Ejemplo de test para VerifyEmailPage

```jsx
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { VerifyEmailPage } from './VerifyEmailPage';
import { authApi } from '../services/api';

jest.mock('../services/api');

describe('VerifyEmailPage', () => {
  test('muestra éxito cuando la verificación es correcta', async () => {
    authApi.verifyEmail.mockResolvedValue({
      data: { message: 'Email verificado', email_verified: true }
    });

    render(
      <BrowserRouter>
        <VerifyEmailPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('¡Email Verificado!')).toBeInTheDocument();
    });
  });

  test('muestra error cuando el token es inválido', async () => {
    authApi.verifyEmail.mockRejectedValue({
      response: { data: { detail: 'Token inválido' } }
    });

    render(
      <BrowserRouter>
        <VerifyEmailPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Error en la Verificación')).toBeInTheDocument();
    });
  });
});
```

## 🔧 Troubleshooting

### El email no llega
1. Verificar configuración de Mailgun en el backend
2. Revisar carpeta de spam
3. Verificar que `FRONTEND_URL` esté correctamente configurado en el backend

### Error CORS con httpOnly cookies
**Causa**: Las httpOnly cookies requieren configuración CORS específica.

**Solución en el backend** (ya configurado en v1.8.0+):

```python
# Backend: main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://app.rydercupfriends.com",
        "https://www.rydercupfriends.com"
    ],
    allow_credentials=True,  # ✅ CRÍTICO para httpOnly cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Solución en el frontend**:

```javascript
// Axios
const api = axios.create({
  withCredentials: true  // ✅ Necesario
});

// Fetch
fetch(url, {
  credentials: 'include'  // ✅ Necesario
});
```

### Las cookies no se guardan en el navegador
1. **Verificar dominio**: En desarrollo local, usa `http://localhost:XXXX` (no `127.0.0.1`)
2. **Verificar HTTPS**: En producción, el backend debe usar HTTPS (las cookies `Secure` solo funcionan con HTTPS)
3. **Verificar SameSite**: El backend configura `SameSite=Lax` para compatibilidad cross-site
4. **Verificar DevTools**: Abre `Application` → `Cookies` → `http://localhost:8000` para ver las cookies

### "401 Unauthorized" después del login
1. **Verificar que `withCredentials: true` esté configurado** en todas las requests
2. **Verificar que el navegador acepte cookies de terceros** (si frontend y backend están en dominios diferentes)
3. **Verificar que las cookies no hayan expirado** (access_token: 15min, refresh_token: 7 días)

### Token no se extrae de la URL
Verificar que estás usando `react-router-dom` v6+:

```jsx
import { useSearchParams } from 'react-router-dom';

const [searchParams] = useSearchParams();
const token = searchParams.get('token');
```

## 📚 Documentación Adicional

- **[Guía de Integración Completa](../EMAIL_VERIFICATION_INTEGRATION.md)**: Documentación detallada
- **[API Reference](../API.md)**: Endpoints y respuestas
- **[Backend README](../../README.md)**: Información del backend

## 🔄 Migración desde localStorage (v1.7.0 → v1.8.0+)

### Checklist de migración

#### 1. Actualizar axios instance
```javascript
// ❌ ANTES
const api = axios.create({
  baseURL: API_BASE_URL,
});

// Interceptor que añadía token manualmente
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ✅ DESPUÉS
const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,  // Las cookies se envían automáticamente
});
```

#### 2. Actualizar login handler
```javascript
// ❌ ANTES
const handleLogin = async (credentials) => {
  const response = await authApi.login(credentials);
  localStorage.setItem('access_token', response.data.access_token);
  localStorage.setItem('refresh_token', response.data.refresh_token);
  navigate('/dashboard');
};

// ✅ DESPUÉS
const handleLogin = async (credentials) => {
  const response = await authApi.login(credentials);
  // Las cookies httpOnly se establecen automáticamente
  navigate('/dashboard');
};
```

#### 3. Actualizar logout handler
```javascript
// ❌ ANTES
const handleLogout = async () => {
  await authApi.logout();
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  navigate('/login');
};

// ✅ DESPUÉS
const handleLogout = async () => {
  await authApi.logout();
  // El backend limpia las cookies automáticamente
  navigate('/login');
};
```

#### 4. Actualizar verificación de autenticación
```javascript
// ❌ ANTES (síncrono pero inseguro)
const isAuthenticated = () => {
  return !!localStorage.getItem('access_token');
};

// ✅ DESPUÉS (asíncrono pero seguro)
const checkAuthentication = async () => {
  try {
    await authApi.getCurrentUser();
    return true;
  } catch {
    return false;
  }
};

// Uso en componente
useEffect(() => {
  const verifyAuth = async () => {
    const authenticated = await checkAuthentication();
    if (!authenticated) {
      navigate('/login');
    }
  };
  verifyAuth();
}, []);
```

#### 5. Limpiar localStorage existente
```javascript
// Ejecutar una vez para limpiar tokens antiguos
localStorage.removeItem('access_token');
localStorage.removeItem('refresh_token');
```

### Ventajas de httpOnly cookies

✅ **Seguridad contra XSS**: JavaScript no puede acceder a las cookies  
✅ **Seguridad contra CSRF**: Backend valida con SameSite=Lax  
✅ **Gestión automática**: El navegador envía las cookies automáticamente  
✅ **Renovación transparente**: El refresh token también está en cookie httpOnly  
✅ **Logout seguro**: El backend invalida las cookies del lado del servidor

## 🤝 Soporte

¿Problemas o preguntas?
- **Backend**: [RyderCupAM Issues](https://github.com/agustinEDev/RyderCupAM/issues)
- **Frontend**: [RyderCupWeb Issues](https://github.com/agustinEDev/RyderCupWeb/issues)

---

✨ **Listo para copiar y usar!**
