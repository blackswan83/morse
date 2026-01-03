import { useState } from 'react';
import { useAppStore } from '../store';
import {
  isWebAuthnSupported,
  authenticateWebAuthn,
  authenticateTrezor,
  getStoredHardwareKeys,
} from '../lib/hardwareKey';

interface HardwareKeyLoginProps {
  username: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function HardwareKeyLogin({ username, onSuccess, onCancel }: HardwareKeyLoginProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<'webauthn' | 'trezor' | null>(null);
  const { loginWithHardwareKey } = useAppStore();

  const storedKeys = getStoredHardwareKeys();
  const hasWebAuthn = storedKeys.some(k => k.type === 'webauthn');
  const hasTrezor = storedKeys.some(k => k.type === 'trezor');
  const webAuthnSupported = isWebAuthnSupported();

  const handleWebAuthnLogin = async () => {
    setIsLoading(true);
    setError(null);
    setMethod('webauthn');

    try {
      // Get authentication options from server
      const optionsResponse = await fetch('/api/webauthn/authenticate/options', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });

      if (!optionsResponse.ok) {
        const data = await optionsResponse.json();
        throw new Error(data.error || 'Failed to get authentication options');
      }

      const options = await optionsResponse.json();

      // Start WebAuthn authentication
      const authentication = await authenticateWebAuthn(options);

      // Verify with server
      const verifyResponse = await fetch('/api/webauthn/authenticate/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          response: authentication,
        }),
      });

      if (!verifyResponse.ok) {
        throw new Error('Authentication failed');
      }

      const result = await verifyResponse.json();

      // Login to socket with session token
      const loginResult = await loginWithHardwareKey(result.sessionToken);

      if (loginResult.success) {
        onSuccess();
      } else {
        throw new Error(loginResult.error || 'Failed to establish connection');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'WebAuthn authentication failed');
    } finally {
      setIsLoading(false);
      setMethod(null);
    }
  };

  const handleTrezorLogin = async () => {
    setIsLoading(true);
    setError(null);
    setMethod('trezor');

    try {
      // Get stored Trezor address
      const trezorKey = storedKeys.find(k => k.type === 'trezor');
      if (!trezorKey) {
        throw new Error('No Trezor key found');
      }

      // First, we need to get the Trezor address by authenticating
      const trezorResult = await authenticateTrezor('');

      // Get challenge from server
      const challengeResponse = await fetch('/api/trezor/authenticate/challenge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          address: trezorResult.address,
        }),
      });

      if (!challengeResponse.ok) {
        const data = await challengeResponse.json();
        throw new Error(data.error || 'Failed to get challenge');
      }

      const { challenge } = await challengeResponse.json();

      // Sign the challenge with Trezor
      const signResult = await authenticateTrezor(challenge);

      // Verify with server
      const verifyResponse = await fetch('/api/trezor/authenticate/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          address: signResult.address,
          signature: signResult.signature,
          challenge,
        }),
      });

      if (!verifyResponse.ok) {
        throw new Error('Trezor authentication failed');
      }

      const result = await verifyResponse.json();

      // Login to socket with session token
      const loginResult = await loginWithHardwareKey(result.sessionToken);

      if (loginResult.success) {
        onSuccess();
      } else {
        throw new Error(loginResult.error || 'Failed to establish connection');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trezor authentication failed');
    } finally {
      setIsLoading(false);
      setMethod(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="text-center mb-4">
        <h3 className="text-lg font-medium text-white">Login with Hardware Key</h3>
        <p className="text-sm text-morse-400">Use your registered security key or Trezor</p>
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {(hasWebAuthn || !hasTrezor) && (
          <button
            onClick={handleWebAuthnLogin}
            disabled={!webAuthnSupported || isLoading}
            className="w-full p-4 bg-morse-800 hover:bg-morse-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center space-x-4 transition-colors"
          >
            <div className="w-12 h-12 bg-morse-600/30 rounded-lg flex items-center justify-center">
              {method === 'webauthn' ? (
                <svg className="animate-spin w-6 h-6 text-morse-400" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-6 h-6 text-morse-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
              )}
            </div>
            <div className="text-left">
              <div className="font-medium text-white">YubiKey / Security Key</div>
              <div className="text-sm text-morse-400">
                {!webAuthnSupported ? 'Not supported in this browser' : 'Touch your security key to login'}
              </div>
            </div>
          </button>
        )}

        {(hasTrezor || !hasWebAuthn) && (
          <button
            onClick={handleTrezorLogin}
            disabled={isLoading}
            className="w-full p-4 bg-morse-800 hover:bg-morse-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center space-x-4 transition-colors"
          >
            <div className="w-12 h-12 bg-morse-600/30 rounded-lg flex items-center justify-center">
              {method === 'trezor' ? (
                <svg className="animate-spin w-6 h-6 text-morse-400" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-6 h-6 text-morse-400" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L4 6v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V6l-8-4zm0 2.18l6 3v5.82c0 4.53-3.13 8.79-6 9.82V4.18z" />
                </svg>
              )}
            </div>
            <div className="text-left">
              <div className="font-medium text-white">Trezor</div>
              <div className="text-sm text-morse-400">Confirm on your Trezor device</div>
            </div>
          </button>
        )}
      </div>

      <button
        onClick={onCancel}
        disabled={isLoading}
        className="w-full text-center text-sm text-morse-400 hover:text-white py-2"
      >
        Cancel
      </button>
    </div>
  );
}
