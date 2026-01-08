import { useState, useEffect } from 'react';
import { useAppStore } from '../store';
import {
  isWebAuthnSupported,
  registerWebAuthn,
  registerTrezor,
  storeHardwareKey,
  removeHardwareKey,
} from '../lib/hardwareKey';
import { logger } from '../lib/logger';

interface HardwareKey {
  id: string;
  type: 'webauthn' | 'trezor';
  name: string;
  address?: string;
  createdAt: number;
}

export function HardwareKeyManager() {
  const { username } = useAppStore();
  const [keys, setKeys] = useState<HardwareKey[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [keyName, setKeyName] = useState('');
  const [addingType, setAddingType] = useState<'webauthn' | 'trezor' | null>(null);

  const webAuthnSupported = isWebAuthnSupported();

  useEffect(() => {
    fetchKeys();
  }, [username]);

  const fetchKeys = async () => {
    if (!username) return;

    try {
      const response = await fetch(`/api/users/${username}/hardware-keys`);
      const data = await response.json();

      const allKeys: HardwareKey[] = [
        ...data.webauthn.map((k: HardwareKey) => ({ ...k, type: 'webauthn' as const })),
        ...data.trezor.map((k: HardwareKey) => ({ ...k, type: 'trezor' as const })),
      ];

      setKeys(allKeys);
    } catch (err) {
      logger.error('Failed to fetch hardware keys', err);
    }
  };

  const handleAddWebAuthn = async () => {
    if (!username) return;

    setIsLoading(true);
    setError(null);
    setAddingType('webauthn');

    try {
      // Get registration options from server
      const optionsResponse = await fetch('/api/webauthn/register/options', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });

      if (!optionsResponse.ok) {
        throw new Error('Failed to get registration options');
      }

      const options = await optionsResponse.json();

      // Start WebAuthn registration (will prompt for security key)
      const registration = await registerWebAuthn(options);

      // Verify with server
      const verifyResponse = await fetch('/api/webauthn/register/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          response: registration,
          name: keyName || 'Security Key',
        }),
      });

      if (!verifyResponse.ok) {
        throw new Error('Failed to verify registration');
      }

      const result = await verifyResponse.json();

      // Store locally
      storeHardwareKey({
        type: 'webauthn',
        credentialId: result.credentialId,
        name: keyName || 'Security Key',
        registeredAt: Date.now(),
      });

      setSuccess('Security key registered successfully!');
      setKeyName('');
      setShowAddMenu(false);
      fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register security key');
    } finally {
      setIsLoading(false);
      setAddingType(null);
    }
  };

  const handleAddTrezor = async () => {
    if (!username) return;

    setIsLoading(true);
    setError(null);
    setAddingType('trezor');

    try {
      // Register Trezor (will open Trezor Connect popup)
      const trezorResult = await registerTrezor();

      // Save to server
      const response = await fetch('/api/trezor/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          publicKey: trezorResult.publicKey,
          address: trezorResult.address,
          name: keyName || 'Trezor',
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to register Trezor');
      }

      // Store locally
      storeHardwareKey({
        type: 'trezor',
        publicKey: trezorResult.publicKey,
        name: keyName || 'Trezor',
        registeredAt: Date.now(),
      });

      setSuccess('Trezor registered successfully!');
      setKeyName('');
      setShowAddMenu(false);
      fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register Trezor');
    } finally {
      setIsLoading(false);
      setAddingType(null);
    }
  };

  const handleRemoveKey = async (key: HardwareKey) => {
    if (!username) return;

    if (!confirm(`Remove ${key.name}? You won't be able to use it to login anymore.`)) {
      return;
    }

    try {
      await fetch(`/api/users/${username}/hardware-keys/${key.type}/${key.id}`, {
        method: 'DELETE',
      });

      removeHardwareKey(key.id);
      fetchKeys();
    } catch (err) {
      setError('Failed to remove key');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-white font-medium">Hardware Security Keys</h3>
          <p className="text-sm text-morse-400">Use YubiKey or Trezor for secure login</p>
        </div>
        <button
          onClick={() => setShowAddMenu(!showAddMenu)}
          className="btn-secondary text-sm flex items-center space-x-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>Add Key</span>
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400 hover:text-red-300">
            Dismiss
          </button>
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-900/30 border border-green-700 rounded-lg text-green-300 text-sm">
          {success}
          <button onClick={() => setSuccess(null)} className="ml-2 text-green-400 hover:text-green-300">
            Dismiss
          </button>
        </div>
      )}

      {showAddMenu && (
        <div className="mb-4 p-4 bg-morse-800 rounded-lg space-y-4">
          <div>
            <label className="block text-sm font-medium text-morse-300 mb-2">
              Key Name (optional)
            </label>
            <input
              type="text"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder="My YubiKey"
              className="input-field w-full"
              disabled={isLoading}
            />
          </div>

          <div className="flex space-x-3">
            <button
              onClick={handleAddWebAuthn}
              disabled={!webAuthnSupported || isLoading}
              className="flex-1 p-3 bg-morse-700 hover:bg-morse-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg flex items-center justify-center space-x-2 transition-colors"
            >
              {addingType === 'webauthn' ? (
                <svg className="animate-spin w-5 h-5 text-morse-300" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-morse-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
              )}
              <span className="text-white font-medium">YubiKey / FIDO2</span>
            </button>

            <button
              onClick={handleAddTrezor}
              disabled={isLoading}
              className="flex-1 p-3 bg-morse-700 hover:bg-morse-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg flex items-center justify-center space-x-2 transition-colors"
            >
              {addingType === 'trezor' ? (
                <svg className="animate-spin w-5 h-5 text-morse-300" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-morse-300" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4zm0 2.18l6 3v5.82c0 4.53-3.13 8.79-6 9.82V4.18z" />
                </svg>
              )}
              <span className="text-white font-medium">Trezor</span>
            </button>
          </div>

          {!webAuthnSupported && (
            <p className="text-xs text-amber-400">
              WebAuthn is not supported in this browser. YubiKey registration is disabled.
            </p>
          )}

          <button
            onClick={() => setShowAddMenu(false)}
            className="w-full text-sm text-morse-400 hover:text-white"
          >
            Cancel
          </button>
        </div>
      )}

      {keys.length === 0 ? (
        <div className="text-center py-8 bg-morse-800/50 rounded-lg">
          <div className="w-12 h-12 mx-auto mb-3 bg-morse-700 rounded-full flex items-center justify-center">
            <svg className="w-6 h-6 text-morse-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <p className="text-morse-400 text-sm">No hardware keys registered</p>
          <p className="text-morse-500 text-xs mt-1">Add a security key for enhanced protection</p>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((key) => (
            <div
              key={key.id}
              className="flex items-center justify-between p-3 bg-morse-800/50 rounded-lg"
            >
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-morse-700 rounded-lg flex items-center justify-center">
                  {key.type === 'webauthn' ? (
                    <svg className="w-5 h-5 text-morse-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-morse-400" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4zm0 2.18l6 3v5.82c0 4.53-3.13 8.79-6 9.82V4.18z" />
                    </svg>
                  )}
                </div>
                <div>
                  <div className="text-white font-medium">{key.name}</div>
                  <div className="text-xs text-morse-500">
                    {key.type === 'webauthn' ? 'Security Key' : 'Trezor'}
                    {key.address && ` • ${key.address.slice(0, 6)}...${key.address.slice(-4)}`}
                    {' • Added '}
                    {new Date(key.createdAt).toLocaleDateString()}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleRemoveKey(key)}
                className="p-2 text-morse-400 hover:text-red-400 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
