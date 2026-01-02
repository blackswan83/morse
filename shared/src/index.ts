// Shared types for Morse secure messaging

export interface User {
  username: string;
  publicKey: string; // Base64 encoded Ed25519 public key
  createdAt: number;
}

export interface KeyBundle {
  identityKey: string; // Ed25519 public key (Base64)
  signedPreKey: string; // X25519 public key (Base64)
  signedPreKeySignature: string; // Signature of prekey (Base64)
  oneTimePreKeys: string[]; // Array of X25519 public keys (Base64)
}

export interface EncryptedMessage {
  id: string;
  senderId: string;
  recipientId: string;
  ciphertext: string; // Base64 encoded
  nonce: string; // Base64 encoded
  ephemeralKey?: string; // For initial key exchange
  timestamp: number;
  type: 'text' | 'key_exchange' | 'ultra_verify';
}

export interface UltraVerificationPayload {
  protocol: 'ultra/1.0';
  username: string;
  identityKey: string;
  ephemeralKey: string;
  timestamp: number;
  nonce: string;
}

export interface Contact {
  username: string;
  publicKey: string;
  sharedSecret?: string; // Derived after key exchange
  verified: boolean; // True if verified via Ultra Protocol
  verifiedAt?: number;
  addedAt: number;
}

// Socket.io Events
export interface ServerToClientEvents {
  message: (msg: EncryptedMessage) => void;
  userOnline: (username: string) => void;
  userOffline: (username: string) => void;
  keyBundle: (bundle: KeyBundle & { username: string }) => void;
  error: (error: { code: string; message: string }) => void;
  registered: (user: { username: string; publicKey: string }) => void;
  contactAdded: (contact: { username: string; publicKey: string }) => void;
}

export interface ClientToServerEvents {
  register: (data: { username: string; publicKey: string; keyBundle: KeyBundle }) => void;
  login: (data: { username: string; signature: string; challenge: string }) => void;
  sendMessage: (msg: Omit<EncryptedMessage, 'id' | 'timestamp'>) => void;
  getKeyBundle: (username: string) => void;
  requestChallenge: (username: string) => void;
  addContact: (username: string) => void;
  getMessages: (since?: number) => void;
}

// Crypto constants
export const CRYPTO_CONSTANTS = {
  IDENTITY_KEY_BYTES: 32,
  SIGNING_KEY_BYTES: 64,
  ENCRYPTION_KEY_BYTES: 32,
  NONCE_BYTES: 24,
  ONE_TIME_PREKEYS_COUNT: 10,
} as const;

// Validation helpers
export function isValidUsername(username: string): boolean {
  return /^[a-zA-Z0-9_]{3,32}$/.test(username);
}

export function isValidBase64(str: string): boolean {
  try {
    return btoa(atob(str)) === str;
  } catch {
    return false;
  }
}
