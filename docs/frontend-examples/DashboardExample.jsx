/**
 * Dashboard Example
 *
 * Ejemplo de cómo mostrar el banner de verificación en el dashboard
 */

import { useState, useEffect } from 'react';
import { EmailVerificationBanner } from '../components/EmailVerificationBanner';
import { authApi } from '../services/api';

export const Dashboard = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const response = await authApi.getCurrentUser();
      setUser(response.data);
    } catch (error) {
      console.error('Error loading user:', error);
      // Redirigir al login si no está autenticado
      window.location.href = '/login';
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Cargando...</div>;
  }

  return (
    <div className="dashboard">

      {/* Banner de verificación de email */}
      {user && !user.email_verified && (
        <EmailVerificationBanner
          userEmail={user.email}
        />
      )}

      {/* Contenido del dashboard */}
      <h1>Dashboard</h1>
      <p>Bienvenido, {user?.first_name}!</p>

      {/* Opcionalmente, deshabilitar ciertas funcionalidades */}
      {user?.email_verified ? (
        <button>Crear Torneo</button>
      ) : (
        <button disabled title="Verifica tu email para crear torneos">
          Crear Torneo 🔒
        </button>
      )}

    </div>
  );
};

export default Dashboard;
