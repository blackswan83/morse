/**
 * Hardware Key Authentication
 * Supports WebAuthn (YubiKey/FIDO2) and Trezor hardware wallets
 */

import {
  startRegistration,
  startAuthentication,
  browserSupportsWebAuthn,
} from '@simplewebauthn/browser';
import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
  AuthenticationResponseJSON,
} from '@simplewebauthn/browser';

// Trezor types
interface TrezorSignMessageResult {
  success: boolean;
  payload: {
    address?: string;
    signature?: string;
    message?: string;
  } | {
    error?: string;
    code?: string;
  };
}

interface TrezorGetPublicKeyResult {
  success: boolean;
  payload: {
    publicKey?: string;
    path?: number[];
  } | {
    error?: string;
    code?: string;
  };
}

// Type for hardware key info
export interface HardwareKeyInfo {
  type: 'webauthn' | 'trezor';
  credentialId?: string; // For WebAuthn
  publicKey?: string; // For Trezor
  name: string;
  registeredAt: number;
}

// Check WebAuthn support
export function isWebAuthnSupported(): boolean {
  return browserSupportsWebAuthn();
}

// Check if Trezor Connect is available
export async function isTrezorAvailable(): Promise<boolean> {
  try {
    const TrezorConnect = await import('@trezor/connect-web');
    return !!TrezorConnect.default;
  } catch {
    return false;
  }
}

// Initialize Trezor Connect
let trezorInitialized = false;
async function initTrezor(): Promise<void> {
  if (trezorInitialized) return;

  try {
    const TrezorConnect = (await import('@trezor/connect-web')).default;
    await TrezorConnect.init({
      lazyLoad: true,
      manifest: {
        email: 'security@morse.app',
        appUrl: window.location.origin,
      },
    });
    trezorInitialized = true;
  } catch (error) {
    console.error('Failed to initialize Trezor Connect:', error);
    throw new Error('Failed to initialize Trezor Connect');
  }
}

// ============ WebAuthn (YubiKey/FIDO2) ============

export interface WebAuthnRegistrationOptions {
  username: string;
  challenge: string;
  rpId?: string;
  rpName?: string;
}

export async function registerWebAuthn(
  options: PublicKeyCredentialCreationOptionsJSON
): Promise<RegistrationResponseJSON> {
  if (!isWebAuthnSupported()) {
    throw new Error('WebAuthn is not supported in this browser');
  }

  try {
    const response = await startRegistration(options);
    return response;
  } catch (error) {
    if (error instanceof Error) {
      if (error.name === 'NotAllowedError') {
        throw new Error('Registration was cancelled or timed out');
      }
      if (error.name === 'InvalidStateError') {
        throw new Error('This security key is already registered');
      }
    }
    throw error;
  }
}

export async function authenticateWebAuthn(
  options: PublicKeyCredentialRequestOptionsJSON
): Promise<AuthenticationResponseJSON> {
  if (!isWebAuthnSupported()) {
    throw new Error('WebAuthn is not supported in this browser');
  }

  try {
    const response = await startAuthentication(options);
    return response;
  } catch (error) {
    if (error instanceof Error) {
      if (error.name === 'NotAllowedError') {
        throw new Error('Authentication was cancelled or timed out');
      }
    }
    throw error;
  }
}

// ============ Trezor ============

const TREZOR_PATH = "m/44'/60'/0'/0/0"; // Standard Ethereum path for identity

export interface TrezorRegistrationResult {
  publicKey: string;
  address: string;
}

export async function registerTrezor(): Promise<TrezorRegistrationResult> {
  await initTrezor();

  const TrezorConnect = (await import('@trezor/connect-web')).default;

  // Get public key from Trezor
  const result = await TrezorConnect.getPublicKey({
    path: TREZOR_PATH,
    showOnTrezor: true,
  }) as TrezorGetPublicKeyResult;

  if (!result.success) {
    const payload = result.payload as { error?: string };
    throw new Error(payload.error || 'Failed to get public key from Trezor');
  }

  const successPayload = result.payload as { publicKey: string };

  // Also get the address for display purposes
  const addressResult = await TrezorConnect.ethereumGetAddress({
    path: TREZOR_PATH,
    showOnTrezor: false,
  });

  if (!addressResult.success) {
    throw new Error('Failed to get address from Trezor');
  }

  return {
    publicKey: successPayload.publicKey,
    address: (addressResult.payload as { address: string }).address,
  };
}

export interface TrezorAuthenticationResult {
  signature: string;
  address: string;
}

export async function authenticateTrezor(
  challenge: string
): Promise<TrezorAuthenticationResult> {
  await initTrezor();

  const TrezorConnect = (await import('@trezor/connect-web')).default;

  // Sign the challenge with Trezor
  const result = await TrezorConnect.ethereumSignMessage({
    path: TREZOR_PATH,
    message: challenge,
    hex: false,
  }) as TrezorSignMessageResult;

  if (!result.success) {
    const payload = result.payload as { error?: string };
    throw new Error(payload.error || 'Failed to sign with Trezor');
  }

  const successPayload = result.payload as { signature: string; address: string };
  return {
    signature: successPayload.signature,
    address: successPayload.address,
  };
}

// ============ Unified Interface ============

export type HardwareKeyType = 'webauthn' | 'trezor';

export interface HardwareKeyRegistration {
  type: HardwareKeyType;
  webauthn?: RegistrationResponseJSON;
  trezor?: TrezorRegistrationResult;
}

export interface HardwareKeyAuthentication {
  type: HardwareKeyType;
  webauthn?: AuthenticationResponseJSON;
  trezor?: TrezorAuthenticationResult;
}

export async function getAvailableHardwareKeyTypes(): Promise<HardwareKeyType[]> {
  const types: HardwareKeyType[] = [];

  if (isWebAuthnSupported()) {
    types.push('webauthn');
  }

  // Trezor is always potentially available via web
  types.push('trezor');

  return types;
}

// Storage helpers for hardware key info
const HARDWARE_KEYS_STORAGE_KEY = 'morse_hardware_keys';

export function getStoredHardwareKeys(): HardwareKeyInfo[] {
  try {
    const stored = localStorage.getItem(HARDWARE_KEYS_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export function storeHardwareKey(key: HardwareKeyInfo): void {
  const keys = getStoredHardwareKeys();
  keys.push(key);
  localStorage.setItem(HARDWARE_KEYS_STORAGE_KEY, JSON.stringify(keys));
}

export function removeHardwareKey(credentialIdOrPublicKey: string): void {
  const keys = getStoredHardwareKeys();
  const filtered = keys.filter(
    (k) => k.credentialId !== credentialIdOrPublicKey && k.publicKey !== credentialIdOrPublicKey
  );
  localStorage.setItem(HARDWARE_KEYS_STORAGE_KEY, JSON.stringify(filtered));
}

export function clearHardwareKeys(): void {
  localStorage.removeItem(HARDWARE_KEYS_STORAGE_KEY);
}
