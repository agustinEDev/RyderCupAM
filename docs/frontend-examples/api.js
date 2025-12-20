/**
 * API Service
 *
 * Configuración de Axios y endpoints para interactuar con el backend
 * 
 * SEGURIDAD (v1.8.0+): Usa httpOnly cookies para tokens JWT
 * - Los tokens se envían automáticamente desde las cookies del navegador
 * - NO se usa localStorage (vulnerable a XSS)
 * - NO se necesita header Authorization manual
 * - Requiere withCredentials: true para enviar cookies cross-origin
 */

import axios from 'axios';

// Base URL del API - configurable por entorno
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Instancia de Axios configurada
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // 10 segundos
  withCredentials: true, // ✅ CRÍTICO: Envía cookies httpOnly automáticamente
});

// Interceptor de response - manejo de errores globales
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Si el token expiró (401), el backend ya limpió las cookies
    // Solo redirigir al login
    if (error.response?.status === 401) {
      window.location.href = '/login?session_expired=true';
    }
    return Promise.reject(error);
  }
);

/**
 * Authentication API
 */
export const authApi = {
  /**
   * Registrar nuevo usuario
   * @param {Object} data - Datos del usuario
   * @param {string} data.email - Email
   * @param {string} data.password - Password
   * @param {string} data.first_name - Nombre
   * @param {string} data.last_name - Apellido
   * @param {number} [data.manual_handicap] - Handicap manual (opcional)
   */
  register: (data) => {
    return api.post('/api/v1/auth/register', data);
  },

  /**
   * Login de usuario
   * @param {Object} credentials
   * @param {string} credentials.email - Email
   * @param {string} credentials.password - Password
   * @returns {Promise} Response incluye user data (tokens vienen en httpOnly cookies)
   * @note El backend establece cookies automáticamente: access_token (15min) y refresh_token (7 días)
   */
  login: (credentials) => {
    return api.post('/api/v1/auth/login', credentials);
  },

  /**
   * Verificar email con token
   * @param {string} token - Token de verificación
   */
  verifyEmail: (token) => {
    return api.post('/api/v1/auth/verify-email', { token });
  },

  /**
   * Obtener usuario actual (requiere autenticación)
   */
  getCurrentUser: () => {
    return api.get('/api/v1/auth/current-user');
  },

  /**
   * Logout de usuario (requiere autenticación)
   * @note El backend invalida el refresh token y limpia las cookies automáticamente
   */
  logout: () => {
    return api.post('/api/v1/auth/logout', {});
  },

  /**
   * Reenviar email de verificación
   * @param {string} email - Email del usuario
   * @note Este endpoint aún no está implementado en el backend
   */
  resendVerificationEmail: (email) => {
    // TODO: Implementar cuando esté disponible en el backend
    return api.post('/api/v1/auth/resend-verification', { email });
  },
};

/**
 * User API
 */
export const userApi = {
  /**
   * Buscar usuario por email o nombre completo
   * @param {Object} params
   * @param {string} [params.email] - Email
   * @param {string} [params.full_name] - Nombre completo
   */
  search: (params) => {
    return api.post('/api/v1/users/search', params);
  },

  /**
   * Actualizar perfil del usuario (requiere autenticación)
   * @param {Object} data
   * @param {string} [data.first_name] - Nuevo nombre
   * @param {string} [data.last_name] - Nuevo apellido
   */
  updateProfile: (data) => {
    return api.put('/api/v1/users/profile', data);
  },

  /**
   * Actualizar datos de seguridad (requiere autenticación)
   * @param {Object} data
   * @param {string} data.current_password - Password actual
   * @param {string} [data.new_email] - Nuevo email
   * @param {string} [data.new_password] - Nuevo password
   * @param {string} [data.confirm_password] - Confirmación del nuevo password
   */
  updateSecurity: (data) => {
    return api.put('/api/v1/users/security', data);
  },
};

/**
 * Handicap API
 */
export const handicapApi = {
  /**
   * Actualizar handicap desde RFEG
   * @param {Object} data
   * @param {string} data.full_name - Nombre completo del jugador
   * @param {number} [data.fallback_handicap] - Handicap manual si no se encuentra en RFEG
   */
  update: (data) => {
    return api.post('/api/v1/handicaps/update', data);
  },

  /**
   * Actualizar handicap manualmente
   * @param {Object} data
   * @param {string} data.user_id - ID del usuario
   * @param {number} data.handicap - Nuevo handicap
   */
  updateManual: (data) => {
    return api.post('/api/v1/handicaps/update-manual', data);
  },

  /**
   * Actualizar múltiples handicaps
   * @param {Array} users - Array de usuarios con full_name y fallback_handicap
   */
  updateMultiple: (users) => {
    return api.post('/api/v1/handicaps/update-multiple', { users });
  },
};

/**
 * Helper para verificar si el usuario está autenticado
 * @note Con httpOnly cookies, no podemos verificar desde el frontend
 * @note Opción 1: Llamar a /api/v1/auth/current-user y ver si retorna 200 o 401
 * @note Opción 2: Mantener estado local después del login (no persistente)
 * @example
 * // Verificación asíncrona (recomendado)
 * async function checkAuth() {
 *   try {
 *     await authApi.getCurrentUser();
 *     return true; // Autenticado
 *   } catch (error) {
 *     return false; // No autenticado o token expirado
 *   }
 * }
 */
export const checkAuthentication = async () => {
  try {
    await authApi.getCurrentUser();
    return true;
  } catch (error) {
    return false;
  }
};

export default api;
