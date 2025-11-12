# 📦 Frontend Code Examples - Email Verification

Esta carpeta contiene componentes y código de ejemplo listos para usar en el frontend de **RyderCupWeb**.

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
   - Configuración completa de Axios
   - Todos los endpoints del backend
   - Interceptors para JWT
   - Helpers para autenticación

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

### Error CORS
Verificar que el backend tenga configurado el origen del frontend en CORS:

```python
# Backend: main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

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

## 🤝 Soporte

¿Problemas o preguntas?
- **Backend**: [RyderCupAM Issues](https://github.com/agustinEDev/RyderCupAM/issues)
- **Frontend**: [RyderCupWeb Issues](https://github.com/agustinEDev/RyderCupWeb/issues)

---

✨ **Listo para copiar y usar!**
