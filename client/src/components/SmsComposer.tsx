/**
 * SMS Composer Component
 * Allows users to send SMS to real phone numbers
 */

import { useState, useEffect } from 'react';
import { useAppStore } from '../store';
import * as telephony from '../lib/telephony';

interface SmsComposerProps {
  onClose: () => void;
}

interface SmsLog {
  id: string;
  direction: 'inbound' | 'outbound';
  phoneNumber: string;
  body: string;
  status: string;
  costCents: number;
  createdAt: number;
}

export default function SmsComposer({ onClose }: SmsComposerProps) {
  const { username } = useAppStore();
  const [phoneNumber, setPhoneNumber] = useState('');
  const [message, setMessage] = useState('');
  const [credits, setCredits] = useState(0);
  const [isConfigured, setIsConfigured] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'compose' | 'history'>('compose');
  const [smsHistory, setSmsHistory] = useState<SmsLog[]>([]);

  // Initialize
  useEffect(() => {
    async function init() {
      if (!username) return;

      const status = await telephony.getTelephonyStatus();
      setIsConfigured(status.enabled);

      if (status.enabled) {
        const userCredits = await telephony.getCredits(username);
        setCredits(userCredits);

        const history = await telephony.getSmsHistory(username);
        setSmsHistory(history);
      }

      setIsLoading(false);
    }

    init();
  }, [username]);

  const handleSend = async () => {
    if (!phoneNumber || !message || !username) return;

    setError(null);
    setSuccess(null);
    setIsSending(true);

    // Format number with + if needed
    let formattedNumber = phoneNumber;
    if (!formattedNumber.startsWith('+')) {
      if (formattedNumber.length === 10) {
        formattedNumber = '+1' + formattedNumber;
      } else {
        formattedNumber = '+' + formattedNumber;
      }
    }

    const result = await telephony.sendSms(username, formattedNumber, message);

    setIsSending(false);

    if (result.success) {
      setSuccess('Message sent!');
      setMessage('');
      // Refresh credits and history
      const userCredits = await telephony.getCredits(username);
      setCredits(userCredits);
      const history = await telephony.getSmsHistory(username);
      setSmsHistory(history);
    } else {
      setError(result.error || 'Failed to send message');
    }
  };

  const handleAddCredits = async (amount: number) => {
    if (!username) return;
    const success = await telephony.addCredits(username, amount);
    if (success) {
      setCredits((prev) => prev + amount);
    }
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-zinc-900 rounded-xl p-8 max-w-md w-full mx-4">
          <div className="flex items-center justify-center gap-3">
            <div className="animate-spin rounded-full h-6 w-6 border-2 border-emerald-500 border-t-transparent" />
            <span className="text-zinc-300">Loading SMS...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!isConfigured) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-zinc-900 rounded-xl p-8 max-w-md w-full mx-4">
          <h2 className="text-xl font-bold text-white mb-4">SMS Not Available</h2>
          <p className="text-zinc-400 mb-6">
            SMS is not configured on this server. Please contact the administrator.
          </p>
          <button
            onClick={onClose}
            className="w-full py-2 px-4 bg-zinc-700 text-white rounded-lg hover:bg-zinc-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const charCount = message.length;
  const smsCount = Math.ceil(charCount / 160) || 1;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-zinc-900 rounded-xl p-6 max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white">SMS</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Credits */}
        <div className="bg-zinc-800 rounded-lg p-3 mb-4 flex items-center justify-between">
          <span className="text-zinc-400 text-sm">Balance</span>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-mono">{telephony.formatCredits(credits)}</span>
            <button
              onClick={() => handleAddCredits(500)}
              className="text-xs px-2 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-500"
            >
              +$5
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setActiveTab('compose')}
            className={`flex-1 py-2 rounded-lg transition-colors ${
              activeTab === 'compose'
                ? 'bg-emerald-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            }`}
          >
            Compose
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`flex-1 py-2 rounded-lg transition-colors ${
              activeTab === 'history'
                ? 'bg-emerald-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            }`}
          >
            History
          </button>
        </div>

        {activeTab === 'compose' ? (
          <>
            {/* Phone number input */}
            <div className="mb-4">
              <label className="block text-sm text-zinc-400 mb-1">To</label>
              <input
                type="tel"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value.replace(/[^0-9+]/g, ''))}
                placeholder="+1 (555) 123-4567"
                className="w-full px-4 py-3 bg-zinc-800 rounded-lg text-white font-mono outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {/* Message input */}
            <div className="mb-4">
              <label className="block text-sm text-zinc-400 mb-1">Message</label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Type your message..."
                rows={4}
                maxLength={1600}
                className="w-full px-4 py-3 bg-zinc-800 rounded-lg text-white outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
              />
              <div className="flex justify-between text-xs text-zinc-500 mt-1">
                <span>{charCount} characters</span>
                <span>{smsCount} SMS segment{smsCount > 1 ? 's' : ''} (${(smsCount * 0.01).toFixed(2)})</span>
              </div>
            </div>

            {/* Send button */}
            <button
              onClick={handleSend}
              disabled={!phoneNumber || !message || credits < smsCount || isSending}
              className="w-full py-3 px-4 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {isSending ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                  Sending...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  Send SMS
                </>
              )}
            </button>

            {/* Success/Error messages */}
            {success && (
              <div className="mt-4 p-3 bg-emerald-900/50 border border-emerald-500 rounded-lg text-emerald-300 text-sm text-center">
                {success}
              </div>
            )}

            {error && (
              <div className="mt-4 p-3 bg-red-900/50 border border-red-500 rounded-lg text-red-300 text-sm text-center">
                {error}
              </div>
            )}

            {/* Credit warning */}
            {credits < smsCount && (
              <div className="mt-4 p-3 bg-yellow-900/50 border border-yellow-500 rounded-lg text-yellow-300 text-sm text-center">
                Insufficient credits. Add credits to send SMS.
              </div>
            )}
          </>
        ) : (
          /* History tab */
          <div className="max-h-80 overflow-y-auto">
            {smsHistory.length === 0 ? (
              <div className="text-center text-zinc-500 py-8">
                No SMS history
              </div>
            ) : (
              <div className="space-y-2">
                {smsHistory.map((sms) => (
                  <div
                    key={sms.id}
                    className="bg-zinc-800 rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-white font-mono text-sm">
                        {telephony.formatPhoneDisplay(sms.phoneNumber)}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-1 rounded ${
                          sms.status === 'delivered' ? 'bg-emerald-900/50 text-emerald-400' :
                          sms.status === 'sent' ? 'bg-blue-900/50 text-blue-400' :
                          sms.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                          'bg-zinc-700 text-zinc-400'
                        }`}>
                          {sms.status}
                        </span>
                        {sms.direction === 'outbound' ? (
                          <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16l-4-4m0 0l4-4m-4 4h18" />
                          </svg>
                        )}
                      </div>
                    </div>
                    <p className="text-zinc-300 text-sm line-clamp-2">{sms.body}</p>
                    <div className="text-xs text-zinc-500 mt-1">
                      {new Date(sms.createdAt).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
