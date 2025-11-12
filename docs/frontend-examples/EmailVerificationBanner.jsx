/**
 * Email Verification Banner
 *
 * Banner persistente que se muestra cuando el usuario no ha verificado su email.
 * Aparece en todas las páginas hasta que se complete la verificación.
 */

import { useState } from 'react';
import './EmailVerificationBanner.css';

export const EmailVerificationBanner = ({ userEmail, onResend }) => {
  const [isResending, setIsResending] = useState(false);
  const [message, setMessage] = useState('');

  const handleResend = async () => {
    setIsResending(true);
    setMessage('');

    try {
      // Si se proporciona un callback onResend, usarlo
      if (onResend) {
        await onResend();
      } else {
        // TODO: Implementar cuando el backend tenga el endpoint
        // await authApi.resendVerificationEmail(userEmail);

        // Por ahora, simular
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      setMessage('✓ Email de verificación enviado');
    } catch (error) {
      setMessage('✗ Error al enviar. Intenta más tarde.');
      console.error('Error resending email:', error);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="email-verification-banner">
      <div className="banner-content">
        <div className="banner-icon">⚠️</div>

        <div className="banner-text">
          <strong>Verifica tu email</strong>
          <p>
            Hemos enviado un email de verificación a <strong>{userEmail}</strong>.
            Por favor revisa tu bandeja de entrada y haz clic en el enlace para verificar tu cuenta.
          </p>
        </div>

        <div className="banner-actions">
          <button
            className="btn-resend"
            onClick={handleResend}
            disabled={isResending}
          >
            {isResending ? 'Enviando...' : 'Reenviar Email'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`banner-message ${message.includes('✓') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}
    </div>
  );
};

export default EmailVerificationBanner;
