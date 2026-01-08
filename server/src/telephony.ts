/**
 * Telephony Service - Twilio Integration
 * Handles VoIP calls and SMS to real phone numbers
 */

import Twilio from 'twilio';
import { v4 as uuidv4 } from 'uuid';
import { logger } from './logger.js';
import {
  getPhoneCredits,
  addCredits,
  deductCredits,
  saveCallLog,
  updateCallLog,
  getCallLogsByUsername,
  getCallLogByTwilioSid,
  saveSmsLog,
  updateSmsLog,
  getSmsLogsByUsername,
} from './db.js';

// Twilio configuration from environment variables
const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID || '';
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN || '';
const TWILIO_API_KEY = process.env.TWILIO_API_KEY || '';
const TWILIO_API_SECRET = process.env.TWILIO_API_SECRET || '';
const TWILIO_PHONE_NUMBER = process.env.TWILIO_PHONE_NUMBER || '';
const TWILIO_TWIML_APP_SID = process.env.TWILIO_TWIML_APP_SID || '';

// Pricing in cents (approximate, actual prices vary by destination)
const PRICING = {
  OUTBOUND_CALL_PER_MIN: 2, // $0.02/min
  OUTBOUND_SMS: 1, // $0.01/SMS
  INBOUND_CALL_PER_MIN: 1, // $0.01/min
  INBOUND_SMS: 1, // $0.01/SMS
};

// Initialize Twilio client
let twilioClient: Twilio.Twilio | null = null;

export function initTwilio(): boolean {
  if (!TWILIO_ACCOUNT_SID || !TWILIO_AUTH_TOKEN) {
    logger.warn('Twilio credentials not configured. Telephony features disabled.');
    return false;
  }

  try {
    twilioClient = Twilio(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN);
    logger.info('Twilio client initialized successfully');
    return true;
  } catch (error) {
    logger.error('Failed to initialize Twilio', error);
    return false;
  }
}

export function isTwilioConfigured(): boolean {
  return twilioClient !== null && !!TWILIO_PHONE_NUMBER;
}

// Generate access token for Twilio Voice SDK (browser-based calling)
export function generateVoiceToken(username: string): string | null {
  if (!TWILIO_ACCOUNT_SID || !TWILIO_API_KEY || !TWILIO_API_SECRET) {
    return null;
  }

  const AccessToken = Twilio.jwt.AccessToken;
  const VoiceGrant = AccessToken.VoiceGrant;

  const token = new AccessToken(
    TWILIO_ACCOUNT_SID,
    TWILIO_API_KEY,
    TWILIO_API_SECRET,
    { identity: username, ttl: 3600 }
  );

  const voiceGrant = new VoiceGrant({
    outgoingApplicationSid: TWILIO_TWIML_APP_SID,
    incomingAllow: true,
  });

  token.addGrant(voiceGrant);

  return token.toJwt();
}

// Get user's phone credit balance
export function getCredits(username: string): number {
  const credits = getPhoneCredits.get(username) as { balanceCents: number } | undefined;
  return credits?.balanceCents || 0;
}

// Add credits to user's balance (in cents)
export function addUserCredits(username: string, amountCents: number): boolean {
  try {
    addCredits.run({
      username,
      amount: amountCents,
      updatedAt: Date.now(),
    });
    return true;
  } catch (error) {
    logger.error('Failed to add credits', error);
    return false;
  }
}

// Check if user has sufficient credits
export function hasCredits(username: string, amountCents: number): boolean {
  return getCredits(username) >= amountCents;
}

// Deduct credits from user's balance
export function deductUserCredits(username: string, amountCents: number): boolean {
  try {
    const result = deductCredits.run({
      username,
      amount: amountCents,
      updatedAt: Date.now(),
    });
    return result.changes > 0;
  } catch (error) {
    logger.error('Failed to deduct credits', error);
    return false;
  }
}

// Send SMS
export async function sendSms(
  username: string,
  toNumber: string,
  body: string
): Promise<{ success: boolean; messageId?: string; error?: string }> {
  if (!twilioClient || !TWILIO_PHONE_NUMBER) {
    return { success: false, error: 'Telephony not configured' };
  }

  // Check credits
  if (!hasCredits(username, PRICING.OUTBOUND_SMS)) {
    return { success: false, error: 'Insufficient credits' };
  }

  const logId = uuidv4();

  try {
    // Send via Twilio
    const message = await twilioClient.messages.create({
      body,
      from: TWILIO_PHONE_NUMBER,
      to: toNumber,
    });

    // Log the SMS
    saveSmsLog.run({
      id: logId,
      username,
      direction: 'outbound',
      phoneNumber: toNumber,
      body,
      status: message.status,
      twilioSid: message.sid,
      createdAt: Date.now(),
    });

    // Deduct credits
    deductUserCredits(username, PRICING.OUTBOUND_SMS);

    return { success: true, messageId: logId };
  } catch (error) {
    logger.error('Failed to send SMS', error);

    // Log the failed attempt
    saveSmsLog.run({
      id: logId,
      username,
      direction: 'outbound',
      phoneNumber: toNumber,
      body,
      status: 'failed',
      twilioSid: null,
      createdAt: Date.now(),
    });

    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to send SMS',
    };
  }
}

// Initiate outbound call (returns call ID for tracking)
export async function initiateCall(
  username: string,
  toNumber: string,
  callbackUrl: string
): Promise<{ success: boolean; callId?: string; error?: string }> {
  if (!twilioClient || !TWILIO_PHONE_NUMBER) {
    return { success: false, error: 'Telephony not configured' };
  }

  // Check credits (require at least 1 minute)
  if (!hasCredits(username, PRICING.OUTBOUND_CALL_PER_MIN)) {
    return { success: false, error: 'Insufficient credits' };
  }

  const callId = uuidv4();

  try {
    const call = await twilioClient.calls.create({
      url: `${callbackUrl}/twiml/outbound`,
      to: toNumber,
      from: TWILIO_PHONE_NUMBER,
      statusCallback: `${callbackUrl}/webhook/call-status`,
      statusCallbackEvent: ['initiated', 'ringing', 'answered', 'completed'],
      statusCallbackMethod: 'POST',
    });

    // Log the call
    saveCallLog.run({
      id: callId,
      username,
      direction: 'outbound',
      phoneNumber: toNumber,
      status: call.status,
      twilioSid: call.sid,
      startedAt: Date.now(),
    });

    return { success: true, callId };
  } catch (error) {
    logger.error('Failed to initiate call', error);

    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to initiate call',
    };
  }
}

// Handle call status webhook
export function handleCallStatusWebhook(data: {
  CallSid: string;
  CallStatus: string;
  CallDuration?: string;
}): void {
  const callLog = getCallLogByTwilioSid.get(data.CallSid) as {
    id: string;
    username: string;
    direction: string;
  } | undefined;

  if (!callLog) {
    logger.warn('Call log not found for SID', { callSid: data.CallSid });
    return;
  }

  const durationSeconds = parseInt(data.CallDuration || '0', 10);
  const costCents = Math.ceil(durationSeconds / 60) * PRICING.OUTBOUND_CALL_PER_MIN;

  updateCallLog.run({
    id: callLog.id,
    status: data.CallStatus,
    durationSeconds,
    costCents,
    endedAt: data.CallStatus === 'completed' ? Date.now() : null,
  });

  // Deduct credits for the call duration
  if (data.CallStatus === 'completed' && durationSeconds > 0) {
    deductUserCredits(callLog.username, costCents);
  }
}

// Handle SMS status webhook
export function handleSmsStatusWebhook(data: {
  MessageSid: string;
  MessageStatus: string;
}): void {
  const smsLog = getSmsLogsByUsername.get(data.MessageSid) as {
    id: string;
    username: string;
  } | undefined;

  if (!smsLog) {
    return;
  }

  updateSmsLog.run({
    id: smsLog.id,
    status: data.MessageStatus,
    costCents: PRICING.OUTBOUND_SMS,
  });
}

// Get call history for a user
export function getCallHistory(username: string): Array<{
  id: string;
  direction: string;
  phoneNumber: string;
  status: string;
  durationSeconds: number;
  costCents: number;
  startedAt: number;
  endedAt: number | null;
}> {
  return getCallLogsByUsername.all(username) as Array<{
    id: string;
    direction: string;
    phoneNumber: string;
    status: string;
    durationSeconds: number;
    costCents: number;
    startedAt: number;
    endedAt: number | null;
  }>;
}

// Get SMS history for a user
export function getSmsHistory(username: string): Array<{
  id: string;
  direction: string;
  phoneNumber: string;
  body: string;
  status: string;
  costCents: number;
  createdAt: number;
}> {
  return getSmsLogsByUsername.all(username) as Array<{
    id: string;
    direction: string;
    phoneNumber: string;
    body: string;
    status: string;
    costCents: number;
    createdAt: number;
  }>;
}

// Generate TwiML for outbound calls
export function generateOutboundTwiML(toNumber: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial callerId="${TWILIO_PHONE_NUMBER}">
    <Number>${toNumber}</Number>
  </Dial>
</Response>`;
}

// Generate TwiML for browser client
export function generateClientTwiML(toNumber: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial callerId="${TWILIO_PHONE_NUMBER}">
    <Number>${toNumber}</Number>
  </Dial>
</Response>`;
}

// Validate phone number format (basic validation)
export function isValidPhoneNumber(number: string): boolean {
  // E.164 format: +[country code][number]
  const e164Regex = /^\+[1-9]\d{6,14}$/;
  return e164Regex.test(number);
}

// Format phone number to E.164
export function formatPhoneNumber(number: string, defaultCountryCode = '1'): string {
  // Remove all non-digit characters
  let digits = number.replace(/\D/g, '');

  // If doesn't start with country code, add default
  if (!number.startsWith('+')) {
    if (digits.length === 10) {
      digits = defaultCountryCode + digits;
    }
    return '+' + digits;
  }

  return '+' + digits;
}
