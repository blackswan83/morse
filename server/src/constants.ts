/**
 * Application Constants
 * Centralized configuration values to avoid magic numbers
 */

export const AUTH = {
  CHALLENGE_EXPIRY_SECONDS: 300, // 5 minutes
  SESSION_TOKEN_EXPIRY_SECONDS: 60, // 1 minute
  WEBAUTHN_CHALLENGE_EXPIRY_MS: 5 * 60 * 1000, // 5 minutes
} as const;

export const VALIDATION = {
  USERNAME_MIN_LENGTH: 3,
  USERNAME_MAX_LENGTH: 32,
  USERNAME_PATTERN: /^[a-zA-Z0-9_]+$/,
  SMS_MAX_LENGTH: 1600,
  PHONE_NUMBER_PATTERN: /^\+[1-9]\d{6,14}$/,
} as const;

export const RATE_LIMITS = {
  // Requests per window
  GENERAL: { windowMs: 60 * 1000, max: 100 }, // 100 req/min
  AUTH: { windowMs: 15 * 60 * 1000, max: 10 }, // 10 attempts per 15 min
  SMS: { windowMs: 60 * 1000, max: 10 }, // 10 SMS/min
  CALL: { windowMs: 60 * 1000, max: 5 }, // 5 calls/min
} as const;

export const LIMITS = {
  JSON_BODY_SIZE: '100kb',
  URL_ENCODED_SIZE: '100kb',
} as const;
