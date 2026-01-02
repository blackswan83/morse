import { useState } from 'react';

interface RecoveryPhraseModalProps {
  phrase: string;
  onClose: () => void;
}

export function RecoveryPhraseModal({ phrase, onClose }: RecoveryPhraseModalProps) {
  const [confirmed, setConfirmed] = useState(false);
  const words = phrase.split(' ');

  const handleCopy = async () => {
    await navigator.clipboard.writeText(phrase);
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
      <div className="card max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center space-x-3 mb-6">
          <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center">
            <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">Recovery Phrase</h2>
            <p className="text-sm text-morse-400">Save this phrase securely</p>
          </div>
        </div>

        <div className="bg-morse-950 rounded-lg p-4 mb-4">
          <div className="grid grid-cols-4 gap-2">
            {words.map((word, index) => (
              <div key={index} className="flex items-center space-x-2 bg-morse-900 rounded px-2 py-1.5">
                <span className="text-xs text-morse-500 w-5">{index + 1}.</span>
                <span className="text-sm text-white font-mono">{word}</span>
              </div>
            ))}
          </div>
        </div>

        <button
          onClick={handleCopy}
          className="btn-secondary w-full mb-4 flex items-center justify-center space-x-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>Copy to Clipboard</span>
        </button>

        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium text-red-300 mb-2">Important Warning</h3>
          <ul className="text-sm text-red-400 space-y-1">
            <li>- Write this phrase down on paper</li>
            <li>- Never share it with anyone</li>
            <li>- If you lose it, your account cannot be recovered</li>
            <li>- This is your ONLY way to recover your account</li>
          </ul>
        </div>

        <label className="flex items-center space-x-3 mb-4 cursor-pointer">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            className="w-4 h-4 rounded border-morse-600 text-morse-500 focus:ring-morse-500 focus:ring-offset-0 bg-morse-900"
          />
          <span className="text-sm text-morse-300">
            I have securely saved my recovery phrase
          </span>
        </label>

        <button
          onClick={onClose}
          disabled={!confirmed}
          className="btn-primary w-full"
        >
          Continue to Morse
        </button>
      </div>
    </div>
  );
}
