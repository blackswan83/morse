import { useState } from 'react';
import { useAppStore } from '../store';
import { RecoveryPhraseModal } from './RecoveryPhraseModal';

export function Welcome() {
  const [username, setUsername] = useState('');
  const [showRecovery, setShowRecovery] = useState(false);
  const { register, isLoading, error, clearError, recoveryPhrase } = useAppStore();

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;

    const result = await register(username.trim());
    if (result.success && result.recoveryPhrase) {
      setShowRecovery(true);
    }
  };

  const isValidUsername = /^[a-zA-Z0-9_]{3,32}$/.test(username);

  return (
    <div className="h-full flex items-center justify-center bg-morse-950 p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-br from-morse-400 to-morse-600 rounded-2xl flex items-center justify-center">
            <svg className="w-12 h-12 text-white" fill="currentColor" viewBox="0 0 20 20">
              <circle cx="6" cy="10" r="2" />
              <rect x="10" y="8" width="6" height="4" rx="1" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Morse</h1>
          <p className="text-morse-400">Secure end-to-end encrypted messaging</p>
        </div>

        <div className="card">
          <h2 className="text-xl font-semibold text-white mb-6">Create Your Identity</h2>

          <form onSubmit={handleRegister}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-morse-300 mb-2">
                Choose a username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  if (error) clearError();
                }}
                placeholder="satoshi"
                className="input-field w-full"
                disabled={isLoading}
                autoFocus
              />
              <p className="text-xs text-morse-500 mt-2">
                3-32 characters, letters, numbers, and underscores only
              </p>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={!isValidUsername || isLoading}
              className="btn-primary w-full"
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Generating keys...
                </span>
              ) : (
                'Create Identity'
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-morse-800">
            <div className="flex items-start space-x-3 text-sm text-morse-400">
              <svg className="w-5 h-5 text-morse-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              <div>
                <p className="font-medium text-morse-300">No email or phone required</p>
                <p className="mt-1">Your identity is a cryptographic key pair generated locally. Only you control it.</p>
              </div>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-morse-600 mt-6">
          All messages are end-to-end encrypted. We cannot read your messages.
        </p>
      </div>

      {showRecovery && recoveryPhrase && (
        <RecoveryPhraseModal
          phrase={recoveryPhrase}
          onClose={() => setShowRecovery(false)}
        />
      )}
    </div>
  );
}
