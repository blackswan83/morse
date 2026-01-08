/**
 * Input Validation and Sanitization
 * Centralized validation functions for all user input
 */

import { VALIDATION } from './constants.js';

export interface ValidationResult {
  valid: boolean;
  error?: string;
  sanitized?: string;
}

/**
 * Validate and sanitize username
 */
export function validateUsername(username: unknown): ValidationResult {
  if (typeof username !== 'string') {
    return { valid: false, error: 'Username must be a string' };
  }

  const trimmed = username.trim();

  if (trimmed.length < VALIDATION.USERNAME_MIN_LENGTH) {
    return { valid: false, error: `Username must be at least ${VALIDATION.USERNAME_MIN_LENGTH} characters` };
  }

  if (trimmed.length > VALIDATION.USERNAME_MAX_LENGTH) {
    return { valid: false, error: `Username must be at most ${VALIDATION.USERNAME_MAX_LENGTH} characters` };
  }

  if (!VALIDATION.USERNAME_PATTERN.test(trimmed)) {
    return { valid: false, error: 'Username can only contain letters, numbers, and underscores' };
  }

  return { valid: true, sanitized: trimmed };
}

/**
 * Validate phone number (E.164 format)
 */
export function validatePhoneNumber(phone: unknown): ValidationResult {
  if (typeof phone !== 'string') {
    return { valid: false, error: 'Phone number must be a string' };
  }

  // Remove spaces and dashes for normalization
  const normalized = phone.replace(/[\s\-\(\)]/g, '');

  // Add + if missing and starts with country code
  const formatted = normalized.startsWith('+') ? normalized : `+${normalized}`;

  if (!VALIDATION.PHONE_NUMBER_PATTERN.test(formatted)) {
    return { valid: false, error: 'Invalid phone number format. Use E.164 format (e.g., +14155551234)' };
  }

  return { valid: true, sanitized: formatted };
}

/**
 * Validate SMS body
 */
export function validateSmsBody(body: unknown): ValidationResult {
  if (typeof body !== 'string') {
    return { valid: false, error: 'SMS body must be a string' };
  }

  const trimmed = body.trim();

  if (trimmed.length === 0) {
    return { valid: false, error: 'SMS body cannot be empty' };
  }

  if (trimmed.length > VALIDATION.SMS_MAX_LENGTH) {
    return { valid: false, error: `SMS body cannot exceed ${VALIDATION.SMS_MAX_LENGTH} characters` };
  }

  return { valid: true, sanitized: trimmed };
}

/**
 * Validate base64 string
 */
export function validateBase64(value: unknown, fieldName: string): ValidationResult {
  if (typeof value !== 'string') {
    return { valid: false, error: `${fieldName} must be a string` };
  }

  // Check for valid base64 characters
  const base64Regex = /^[A-Za-z0-9+/=_-]+$/;
  if (!base64Regex.test(value)) {
    return { valid: false, error: `${fieldName} contains invalid characters` };
  }

  return { valid: true, sanitized: value };
}

/**
 * Validate UUID
 */
export function validateUuid(value: unknown, fieldName: string): ValidationResult {
  if (typeof value !== 'string') {
    return { valid: false, error: `${fieldName} must be a string` };
  }

  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  if (!uuidRegex.test(value)) {
    return { valid: false, error: `${fieldName} must be a valid UUID` };
  }

  return { valid: true, sanitized: value.toLowerCase() };
}

/**
 * Validate required string field
 */
export function validateRequiredString(value: unknown, fieldName: string, maxLength = 1000): ValidationResult {
  if (typeof value !== 'string') {
    return { valid: false, error: `${fieldName} must be a string` };
  }

  const trimmed = value.trim();

  if (trimmed.length === 0) {
    return { valid: false, error: `${fieldName} is required` };
  }

  if (trimmed.length > maxLength) {
    return { valid: false, error: `${fieldName} cannot exceed ${maxLength} characters` };
  }

  return { valid: true, sanitized: trimmed };
}

/**
 * Validate optional positive integer
 */
export function validatePositiveInteger(value: unknown, fieldName: string): ValidationResult & { value?: number } {
  if (value === undefined || value === null) {
    return { valid: true };
  }

  const num = typeof value === 'string' ? parseInt(value, 10) : value;

  if (typeof num !== 'number' || !Number.isInteger(num) || num <= 0) {
    return { valid: false, error: `${fieldName} must be a positive integer` };
  }

  return { valid: true, value: num };
}

/**
 * Sanitize string to prevent XSS (for display purposes)
 */
export function sanitizeString(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}
