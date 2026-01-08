/**
 * Client-side input validation
 */

export interface ValidationResult {
  valid: boolean;
  error?: string;
  sanitized?: string;
}

// Constants
export const LIMITS = {
  USERNAME_MIN_LENGTH: 3,
  USERNAME_MAX_LENGTH: 32,
  MESSAGE_MAX_LENGTH: 10000,
  SMS_MAX_LENGTH: 1600,
  PHONE_MIN_LENGTH: 10,
  PHONE_MAX_LENGTH: 15,
} as const;

// Username validation
const USERNAME_REGEX = /^[a-zA-Z0-9_-]+$/;

export function validateUsername(username: unknown): ValidationResult {
  if (typeof username !== 'string') {
    return { valid: false, error: 'Username must be a string' };
  }

  const trimmed = username.trim();

  if (trimmed.length < LIMITS.USERNAME_MIN_LENGTH) {
    return { valid: false, error: `Username must be at least ${LIMITS.USERNAME_MIN_LENGTH} characters` };
  }

  if (trimmed.length > LIMITS.USERNAME_MAX_LENGTH) {
    return { valid: false, error: `Username must be at most ${LIMITS.USERNAME_MAX_LENGTH} characters` };
  }

  if (!USERNAME_REGEX.test(trimmed)) {
    return { valid: false, error: 'Username can only contain letters, numbers, underscores, and hyphens' };
  }

  return { valid: true, sanitized: trimmed };
}

// Phone number validation
const PHONE_REGEX = /^\+?[1-9]\d{9,14}$/;

export function validatePhoneNumber(phone: unknown): ValidationResult {
  if (typeof phone !== 'string') {
    return { valid: false, error: 'Phone number must be a string' };
  }

  // Remove spaces and dashes for validation
  const cleaned = phone.replace(/[\s\-()]/g, '');

  if (!PHONE_REGEX.test(cleaned)) {
    return { valid: false, error: 'Invalid phone number format' };
  }

  return { valid: true, sanitized: cleaned };
}

// Message content validation
export function validateMessageContent(content: unknown): ValidationResult {
  if (typeof content !== 'string') {
    return { valid: false, error: 'Message must be a string' };
  }

  const trimmed = content.trim();

  if (trimmed.length === 0) {
    return { valid: false, error: 'Message cannot be empty' };
  }

  if (trimmed.length > LIMITS.MESSAGE_MAX_LENGTH) {
    return { valid: false, error: `Message is too long (max ${LIMITS.MESSAGE_MAX_LENGTH} characters)` };
  }

  return { valid: true, sanitized: trimmed };
}

// SMS body validation
export function validateSmsBody(body: unknown): ValidationResult {
  if (typeof body !== 'string') {
    return { valid: false, error: 'SMS body must be a string' };
  }

  const trimmed = body.trim();

  if (trimmed.length === 0) {
    return { valid: false, error: 'SMS cannot be empty' };
  }

  if (trimmed.length > LIMITS.SMS_MAX_LENGTH) {
    return { valid: false, error: `SMS is too long (max ${LIMITS.SMS_MAX_LENGTH} characters)` };
  }

  return { valid: true, sanitized: trimmed };
}

// Sanitize string to prevent XSS (for display purposes)
export function sanitizeForDisplay(input: string): string {
  const div = document.createElement('div');
  div.textContent = input;
  return div.innerHTML;
}
