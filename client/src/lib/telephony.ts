/**
 * Telephony Service - Client-side Twilio integration
 * Handles VoIP calls and SMS from the browser
 */

import { Device, Call } from '@twilio/voice-sdk';

const API_BASE = 'http://localhost:3001/api/telephony';

interface TelephonyStatus {
  enabled: boolean;
  phoneNumber: string | null;
}

interface CallLog {
  id: string;
  direction: 'inbound' | 'outbound';
  phoneNumber: string;
  status: string;
  durationSeconds: number;
  costCents: number;
  startedAt: number;
  endedAt: number | null;
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

export interface TelephonyState {
  isConfigured: boolean;
  credits: number;
  device: Device | null;
  currentCall: Call | null;
  callState: 'idle' | 'connecting' | 'ringing' | 'connected' | 'disconnected';
  callHistory: CallLog[];
  smsHistory: SmsLog[];
}

let twilioDevice: Device | null = null;
let currentCall: Call | null = null;

// Check if telephony is enabled
export async function getTelephonyStatus(): Promise<TelephonyStatus> {
  try {
    const response = await fetch(`${API_BASE}/status`);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to get telephony status:', error);
    return { enabled: false, phoneNumber: null };
  }
}

// Get user credits balance
export async function getCredits(username: string): Promise<number> {
  try {
    const response = await fetch(`${API_BASE}/credits/${username}`);
    const data = await response.json();
    return data.credits || 0;
  } catch (error) {
    console.error('Failed to get credits:', error);
    return 0;
  }
}

// Add credits to account (for demo, normally would go through payment flow)
export async function addCredits(
  username: string,
  amountCents: number
): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/credits/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, amountCents }),
    });
    const data = await response.json();
    return data.success;
  } catch (error) {
    console.error('Failed to add credits:', error);
    return false;
  }
}

// Initialize Twilio Voice Device
export async function initVoiceDevice(
  username: string,
  onStateChange?: (state: string) => void
): Promise<Device | null> {
  try {
    const response = await fetch(`${API_BASE}/voice-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });

    const data = await response.json();

    if (!data.token) {
      console.error('Failed to get voice token');
      return null;
    }

    twilioDevice = new Device(data.token, {
      codecPreferences: [Call.Codec.Opus, Call.Codec.PCMU],
    });

    twilioDevice.on('registered', () => {
      console.log('Twilio Device registered');
      onStateChange?.('registered');
    });

    twilioDevice.on('error', (error) => {
      console.error('Twilio Device error:', error);
      onStateChange?.('error');
    });

    twilioDevice.on('incoming', (call) => {
      console.log('Incoming call from:', call.parameters.From);
      currentCall = call;
      onStateChange?.('incoming');
    });

    await twilioDevice.register();

    return twilioDevice;
  } catch (error) {
    console.error('Failed to initialize voice device:', error);
    return null;
  }
}

// Make an outbound call
export async function makeCall(
  phoneNumber: string,
  onCallStateChange?: (state: string, call?: Call) => void
): Promise<Call | null> {
  if (!twilioDevice) {
    console.error('Voice device not initialized');
    return null;
  }

  try {
    const call = await twilioDevice.connect({
      params: { To: phoneNumber },
    });

    currentCall = call;

    call.on('accept', () => {
      console.log('Call accepted');
      onCallStateChange?.('connected', call);
    });

    call.on('disconnect', () => {
      console.log('Call disconnected');
      currentCall = null;
      onCallStateChange?.('disconnected');
    });

    call.on('cancel', () => {
      console.log('Call cancelled');
      currentCall = null;
      onCallStateChange?.('cancelled');
    });

    call.on('reject', () => {
      console.log('Call rejected');
      currentCall = null;
      onCallStateChange?.('rejected');
    });

    call.on('error', (error) => {
      console.error('Call error:', error);
      currentCall = null;
      onCallStateChange?.('error');
    });

    call.on('ringing', () => {
      console.log('Call ringing');
      onCallStateChange?.('ringing', call);
    });

    onCallStateChange?.('connecting', call);

    return call;
  } catch (error) {
    console.error('Failed to make call:', error);
    return null;
  }
}

// Answer incoming call
export function answerCall(): boolean {
  if (currentCall) {
    currentCall.accept();
    return true;
  }
  return false;
}

// Reject/hang up call
export function endCall(): boolean {
  if (currentCall) {
    currentCall.disconnect();
    currentCall = null;
    return true;
  }
  return false;
}

// Mute/unmute call
export function muteCall(mute: boolean): boolean {
  if (currentCall) {
    currentCall.mute(mute);
    return true;
  }
  return false;
}

// Get current call state
export function getCurrentCall(): Call | null {
  return currentCall;
}

// Send DTMF tones
export function sendDtmf(digits: string): boolean {
  if (currentCall) {
    currentCall.sendDigits(digits);
    return true;
  }
  return false;
}

// Destroy device on logout
export function destroyDevice(): void {
  if (twilioDevice) {
    twilioDevice.destroy();
    twilioDevice = null;
  }
  currentCall = null;
}

// Send SMS
export async function sendSms(
  username: string,
  toNumber: string,
  body: string
): Promise<{ success: boolean; messageId?: string; error?: string }> {
  try {
    const response = await fetch(`${API_BASE}/sms/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, toNumber, body }),
    });
    return await response.json();
  } catch (error) {
    console.error('Failed to send SMS:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to send SMS',
    };
  }
}

// Get call history
export async function getCallHistory(username: string): Promise<CallLog[]> {
  try {
    const response = await fetch(`${API_BASE}/call/history/${username}`);
    const data = await response.json();
    return data.calls || [];
  } catch (error) {
    console.error('Failed to get call history:', error);
    return [];
  }
}

// Get SMS history
export async function getSmsHistory(username: string): Promise<SmsLog[]> {
  try {
    const response = await fetch(`${API_BASE}/sms/history/${username}`);
    const data = await response.json();
    return data.messages || [];
  } catch (error) {
    console.error('Failed to get SMS history:', error);
    return [];
  }
}

// Format phone number for display
export function formatPhoneDisplay(number: string): string {
  // Remove all non-digit characters
  const digits = number.replace(/\D/g, '');

  if (digits.length === 11 && digits[0] === '1') {
    // US number: +1 (XXX) XXX-XXXX
    return `+1 (${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`;
  } else if (digits.length === 10) {
    // US number without country code
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }

  return number;
}

// Format credits for display
export function formatCredits(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// Format duration for display
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
