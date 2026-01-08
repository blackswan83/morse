/**
 * Phone Dialer Component
 * Allows users to make VoIP calls to real phone numbers
 */

import { useState, useEffect, useCallback } from 'react';
import { Call } from '@twilio/voice-sdk';
import { useAppStore } from '../store';
import * as telephony from '../lib/telephony';
import { logger } from '../lib/logger';

interface PhoneDialerProps {
  onClose: () => void;
}

export default function PhoneDialer({ onClose }: PhoneDialerProps) {
  const { username } = useAppStore();
  const [phoneNumber, setPhoneNumber] = useState('');
  const [credits, setCredits] = useState(0);
  const [isConfigured, setIsConfigured] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [callState, setCallState] = useState<string>('idle');
  const [_currentCall, setCurrentCall] = useState<Call | null>(null);
  const [callDuration, setCallDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'dialer' | 'history'>('dialer');
  const [callHistory, setCallHistory] = useState<telephony.TelephonyState['callHistory']>([]);

  // Initialize telephony
  useEffect(() => {
    async function init() {
      if (!username) return;

      const status = await telephony.getTelephonyStatus();
      setIsConfigured(status.enabled);

      if (status.enabled) {
        const userCredits = await telephony.getCredits(username);
        setCredits(userCredits);

        await telephony.initVoiceDevice(username, (state) => {
          logger.info('Device state changed', { state });
        });

        const history = await telephony.getCallHistory(username);
        setCallHistory(history);
      }

      setIsLoading(false);
    }

    init();

    return () => {
      // Cleanup on unmount
      if (callState !== 'idle') {
        telephony.endCall();
      }
    };
  }, [username]);

  // Call duration timer
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (callState === 'connected') {
      interval = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [callState]);

  const handleDialPad = (digit: string) => {
    if (callState === 'connected') {
      telephony.sendDtmf(digit);
    } else {
      setPhoneNumber((prev) => prev + digit);
    }
  };

  const handleBackspace = () => {
    setPhoneNumber((prev) => prev.slice(0, -1));
  };

  const handleCall = useCallback(async () => {
    if (!phoneNumber) return;

    setError(null);
    setCallDuration(0);

    // Format number with + if needed
    let formattedNumber = phoneNumber;
    if (!formattedNumber.startsWith('+')) {
      if (formattedNumber.length === 10) {
        formattedNumber = '+1' + formattedNumber;
      } else {
        formattedNumber = '+' + formattedNumber;
      }
    }

    const call = await telephony.makeCall(formattedNumber, (state, call) => {
      setCallState(state);
      if (call) setCurrentCall(call);

      if (state === 'disconnected' || state === 'cancelled' || state === 'rejected') {
        setCurrentCall(null);
        // Refresh credits and history
        if (username) {
          telephony.getCredits(username).then(setCredits);
          telephony.getCallHistory(username).then(setCallHistory);
        }
      }
    });

    if (!call) {
      setError('Failed to initiate call');
    }
  }, [phoneNumber, username]);

  const handleHangup = () => {
    telephony.endCall();
    setCallState('idle');
    setCurrentCall(null);
    setIsMuted(false);
  };

  const handleMuteToggle = () => {
    telephony.muteCall(!isMuted);
    setIsMuted(!isMuted);
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
            <span className="text-zinc-300">Loading phone...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!isConfigured) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-zinc-900 rounded-xl p-8 max-w-md w-full mx-4">
          <h2 className="text-xl font-bold text-white mb-4">Phone Not Available</h2>
          <p className="text-zinc-400 mb-6">
            Phone calling is not configured on this server. Please contact the administrator.
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

  const isInCall = ['connecting', 'ringing', 'connected'].includes(callState);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-zinc-900 rounded-xl p-6 max-w-sm w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white">Phone</h2>
          <button
            onClick={onClose}
            disabled={isInCall}
            className="text-zinc-400 hover:text-white disabled:opacity-50"
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
            onClick={() => setActiveTab('dialer')}
            className={`flex-1 py-2 rounded-lg transition-colors ${
              activeTab === 'dialer'
                ? 'bg-emerald-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            }`}
          >
            Dialer
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

        {activeTab === 'dialer' ? (
          <>
            {/* Phone number display */}
            <div className="bg-zinc-800 rounded-lg p-4 mb-4">
              {isInCall ? (
                <div className="text-center">
                  <div className="text-lg text-white font-mono mb-1">
                    {telephony.formatPhoneDisplay(phoneNumber)}
                  </div>
                  <div className="text-sm text-zinc-400">
                    {callState === 'connecting' && 'Connecting...'}
                    {callState === 'ringing' && 'Ringing...'}
                    {callState === 'connected' && telephony.formatDuration(callDuration)}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value.replace(/[^0-9+]/g, ''))}
                    placeholder="+1 (555) 123-4567"
                    className="flex-1 bg-transparent text-xl text-white font-mono outline-none"
                  />
                  {phoneNumber && (
                    <button
                      onClick={handleBackspace}
                      className="text-zinc-400 hover:text-white p-2"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z" />
                      </svg>
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Dial pad */}
            <div className="grid grid-cols-3 gap-2 mb-4">
              {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map((digit) => (
                <button
                  key={digit}
                  onClick={() => handleDialPad(digit)}
                  className="h-14 bg-zinc-800 rounded-lg text-xl font-medium text-white hover:bg-zinc-700 transition-colors"
                >
                  {digit}
                </button>
              ))}
            </div>

            {/* Call controls */}
            <div className="flex justify-center gap-4">
              {isInCall ? (
                <>
                  <button
                    onClick={handleMuteToggle}
                    className={`w-14 h-14 rounded-full flex items-center justify-center ${
                      isMuted ? 'bg-red-600' : 'bg-zinc-700'
                    } text-white hover:opacity-80 transition-opacity`}
                  >
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      {isMuted ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                      )}
                    </svg>
                  </button>
                  <button
                    onClick={handleHangup}
                    className="w-14 h-14 rounded-full bg-red-600 text-white hover:bg-red-500 transition-colors flex items-center justify-center"
                  >
                    <svg className="w-6 h-6 transform rotate-135" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 00-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z" />
                    </svg>
                  </button>
                </>
              ) : (
                <button
                  onClick={handleCall}
                  disabled={!phoneNumber || credits < 2}
                  className="w-14 h-14 rounded-full bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
                >
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 00-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z" />
                  </svg>
                </button>
              )}
            </div>

            {/* Error display */}
            {error && (
              <div className="mt-4 p-3 bg-red-900/50 border border-red-500 rounded-lg text-red-300 text-sm text-center">
                {error}
              </div>
            )}

            {/* Credit warning */}
            {credits < 2 && !isInCall && (
              <div className="mt-4 p-3 bg-yellow-900/50 border border-yellow-500 rounded-lg text-yellow-300 text-sm text-center">
                Insufficient credits. Add credits to make calls.
              </div>
            )}
          </>
        ) : (
          /* History tab */
          <div className="max-h-80 overflow-y-auto">
            {callHistory.length === 0 ? (
              <div className="text-center text-zinc-500 py-8">
                No call history
              </div>
            ) : (
              <div className="space-y-2">
                {callHistory.map((call) => (
                  <div
                    key={call.id}
                    className="bg-zinc-800 rounded-lg p-3 flex items-center justify-between"
                  >
                    <div>
                      <div className="text-white font-mono text-sm">
                        {telephony.formatPhoneDisplay(call.phoneNumber)}
                      </div>
                      <div className="text-xs text-zinc-500">
                        {new Date(call.startedAt).toLocaleString()} · {telephony.formatDuration(call.durationSeconds)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-1 rounded ${
                        call.status === 'completed' ? 'bg-emerald-900/50 text-emerald-400' :
                        call.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                        'bg-zinc-700 text-zinc-400'
                      }`}>
                        {call.status}
                      </span>
                      {call.direction === 'outbound' ? (
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
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
