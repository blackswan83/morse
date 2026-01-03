/**
 * Application Configuration
 * Uses environment variables for production, defaults for development
 */

export const config = {
  // API base URL (REST endpoints)
  apiUrl: import.meta.env.VITE_API_URL || 'http://localhost:3001',

  // WebSocket URL (Socket.io)
  wsUrl: import.meta.env.VITE_WS_URL || 'http://localhost:3001',

  // Check if running in production
  isProduction: import.meta.env.PROD,
};

// Derived URLs
export const API_BASE = `${config.apiUrl}/api`;
export const TELEPHONY_API = `${config.apiUrl}/api/telephony`;
