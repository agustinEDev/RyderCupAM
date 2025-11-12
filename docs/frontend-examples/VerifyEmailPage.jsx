/**
 * Verify Email Page
 *
 * Página que maneja la verificación de email cuando el usuario hace clic
 * en el link recibido por correo.
 *
 * Ruta: /verify-email?token=ABC123
 */

import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import './VerifyEmailPage.css';

// Asume que tienes un servicio API configurado
import { authApi } from '../services/api';

export const VerifyEmailPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [status, setStatus] = useState('verifying'); // verifying | success | error
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');

    if (!token) {
      setStatus('error');
      setMessage('Token de verificación no encontrado en la URL');
      return;
    }

    verifyEmail(token);
  }, [searchParams]);

  const verifyEmail = async (token) => {
    try {
      setStatus('verifying');

      const response = await authApi.verifyEmail(token);

      setStatus('success');
      setMessage(response.data.message || 'Email verificado exitosamente');

      // Redirigir al login después de 3 segundos
      setTimeout(() => {
        navigate('/login?verified=true');
      }, 3000);

    } catch (error) {
      setStatus('error');

      const errorMessage = error.response?.data?.detail
        || 'Error al verificar el email. El token puede ser inválido o haber expirado.';

      setMessage(errorMessage);

      console.error('Error verifying email:', error);
    }
  };

  const handleRetry = () => {
    const token = searchParams.get('token');
    if (token) {
      verifyEmail(token);
    }
  };

  return (
    <div className="verify-email-container">
      <div className="verify-email-card">

        {/* Estado: Verificando */}
        {status === 'verifying' && (
          <div className="verify-state verifying">
            <div className="spinner" />
            <h1>Verificando tu email...</h1>
            <p>Por favor espera un momento mientras confirmamos tu dirección de correo.</p>
          </div>
        )}

        {/* Estado: Éxito */}
        {status === 'success' && (
          <div className="verify-state success">
            <div className="icon success-icon">✓</div>
            <h1>¡Email Verificado!</h1>
            <p className="message">{message}</p>
            <p className="redirect-info">
              Redirigiendo al login en 3 segundos...
            </p>
            <button
              className="btn btn-primary"
              onClick={() => navigate('/login?verified=true')}
            >
              Ir al Login Ahora
            </button>
          </div>
        )}

        {/* Estado: Error */}
        {status === 'error' && (
          <div className="verify-state error">
            <div className="icon error-icon">✕</div>
            <h1>Error en la Verificación</h1>
            <p className="message">{message}</p>
            <div className="error-actions">
              <button
                className="btn btn-secondary"
                onClick={handleRetry}
              >
                Intentar de Nuevo
              </button>
              <button
                className="btn btn-primary"
                onClick={() => navigate('/login')}
              >
                Ir al Login
              </button>
            </div>
            <p className="help-text">
              Si el problema persiste, contacta a soporte o solicita un nuevo email de verificación.
            </p>
          </div>
        )}

      </div>
    </div>
  );
};

export default VerifyEmailPage;
