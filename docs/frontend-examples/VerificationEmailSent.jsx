/**
 * Verification Email Sent Component
 *
 * Componente que se muestra después de un registro exitoso,
 * informando al usuario que debe verificar su email.
 */

import { useState } from 'react';
import './VerificationEmailSent.css';

export const VerificationEmailSent = ({ email, onBackToLogin }) => {
  const [isResending, setIsResending] = useState(false);
  const [resendMessage, setResendMessage] = useState('');

  // Función para reenviar email (implementar cuando esté disponible en el backend)
  const handleResendEmail = async () => {
    setIsResending(true);
    setResendMessage('');

    try {
      // TODO: Implementar cuando el backend tenga el endpoint
      // await authApi.resendVerificationEmail(email);

      // Por ahora, simular
      await new Promise(resolve => setTimeout(resolve, 1000));

      setResendMessage('✓ Email de verificación reenviado exitosamente');
    } catch (error) {
      setResendMessage('✕ Error al reenviar el email. Intenta más tarde.');
      console.error('Error resending email:', error);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="verification-sent-container">
      <div className="verification-sent-card">

        {/* Icono de email */}
        <div className="email-icon">
          <svg
            width="80"
            height="80"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <polyline
              points="22,6 12,13 2,6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        {/* Contenido principal */}
        <h1>¡Registro Exitoso!</h1>

        <p className="main-message">
          Hemos enviado un correo de verificación a:
        </p>

        <p className="email-address">{email}</p>

        <div className="instructions">
          <h3>Próximos pasos:</h3>
          <ol>
            <li>Revisa tu bandeja de entrada</li>
            <li>Busca el email de <strong>Ryder Cup Friends</strong></li>
            <li>Haz clic en el enlace de verificación</li>
          </ol>
        </div>

        <div className="tips">
          <p className="tip">
            💡 <strong>Consejo:</strong> Si no ves el email, revisa tu carpeta de spam o correo no deseado.
          </p>
        </div>

        {/* Botón de reenviar */}
        <div className="resend-section">
          <p className="resend-text">¿No recibiste el email?</p>
          <button
            className="btn btn-secondary"
            onClick={handleResendEmail}
            disabled={isResending}
          >
            {isResending ? 'Reenviando...' : 'Reenviar Email'}
          </button>

          {resendMessage && (
            <p className={`resend-message ${resendMessage.includes('✓') ? 'success' : 'error'}`}>
              {resendMessage}
            </p>
          )}
        </div>

        {/* Botón para ir al login */}
        <button
          className="btn btn-primary"
          onClick={onBackToLogin || (() => window.location.href = '/login')}
        >
          Ir al Login
        </button>

      </div>
    </div>
  );
};

export default VerificationEmailSent;
