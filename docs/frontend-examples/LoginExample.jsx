/**
 * Login Example
 *
 * Ejemplo de cómo manejar el login con verificación de email
 * 
 * SEGURIDAD (v1.8.0+): Usa httpOnly cookies automáticas
 * - NO necesitas guardar tokens en localStorage
 * - Los tokens se envían automáticamente con cada request
 * - El navegador gestiona las cookies de forma segura
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../services/api';

export const LoginPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authApi.login({ email, password });

      // ✅ NO necesitas guardar tokens - las cookies httpOnly se establecieron automáticamente
      // ❌ NO HAGAS: saveAuthToken(response.data.access_token)
      
      // Guardar usuario en estado global (Redux, Context, etc.)
      // setUser(response.data.user);

      // IMPORTANTE: Verificar si necesita confirmar email
      if (response.data.email_verification_required) {
        // Opción 1: Redirigir a una página de advertencia
        navigate('/dashboard?verify_email=true');

        // Opción 2: Mostrar modal
        // showEmailVerificationModal();

        // Opción 3: El banner se mostrará automáticamente en el dashboard
        // (si tienes el componente EmailVerificationBanner)
      } else {
        // Email ya verificado, continuar normalmente
        navigate('/dashboard');
      }

    } catch (error) {
      if (error.response?.status === 401) {
        setError('Email o contraseña incorrectos');
      } else {
        setError('Error al iniciar sesión. Intenta de nuevo.');
      }
      console.error('Login error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <form onSubmit={handleLogin}>
        <h1>Iniciar Sesión</h1>

        {error && <div className="error-message">{error}</div>}

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <input
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
        </button>
      </form>
    </div>
  );
};

export default LoginPage;
