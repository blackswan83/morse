import Database from 'better-sqlite3';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const db = new Database(join(__dirname, '..', 'morse.db'));

// Initialize database schema
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    public_key TEXT NOT NULL UNIQUE,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
  );

  CREATE TABLE IF NOT EXISTS key_bundles (
    username TEXT PRIMARY KEY REFERENCES users(username),
    identity_key TEXT NOT NULL,
    signed_prekey TEXT NOT NULL,
    signed_prekey_signature TEXT NOT NULL,
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
  );

  CREATE TABLE IF NOT EXISTS one_time_prekeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL REFERENCES users(username),
    prekey TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
  );

  CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    sender_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    ciphertext TEXT NOT NULL,
    nonce TEXT NOT NULL,
    ephemeral_key TEXT,
    message_type TEXT NOT NULL DEFAULT 'text',
    timestamp INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    delivered INTEGER NOT NULL DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS challenges (
    username TEXT PRIMARY KEY,
    challenge TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    expires_at INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id, delivered);
  CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
  CREATE INDEX IF NOT EXISTS idx_prekeys_username ON one_time_prekeys(username, used);

  -- Hardware key support (WebAuthn/FIDO2)
  CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL REFERENCES users(username),
    credential_id TEXT NOT NULL UNIQUE,
    credential_public_key BLOB NOT NULL,
    counter INTEGER NOT NULL DEFAULT 0,
    credential_device_type TEXT,
    credential_backed_up INTEGER NOT NULL DEFAULT 0,
    transports TEXT,
    name TEXT NOT NULL DEFAULT 'Security Key',
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
  );

  -- Trezor hardware wallet support
  CREATE TABLE IF NOT EXISTS trezor_keys (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL REFERENCES users(username),
    public_key TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT 'Trezor',
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_webauthn_username ON webauthn_credentials(username);
  CREATE INDEX IF NOT EXISTS idx_trezor_username ON trezor_keys(username);

  -- Telephony support (VoIP calls and SMS)
  CREATE TABLE IF NOT EXISTS phone_credits (
    username TEXT PRIMARY KEY REFERENCES users(username),
    balance_cents INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
  );

  CREATE TABLE IF NOT EXISTS call_logs (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL REFERENCES users(username),
    direction TEXT NOT NULL CHECK(direction IN ('inbound', 'outbound')),
    phone_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'initiated',
    duration_seconds INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0,
    twilio_sid TEXT,
    started_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    ended_at INTEGER
  );

  CREATE TABLE IF NOT EXISTS sms_logs (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL REFERENCES users(username),
    direction TEXT NOT NULL CHECK(direction IN ('inbound', 'outbound')),
    phone_number TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    cost_cents INTEGER DEFAULT 0,
    twilio_sid TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000)
  );

  CREATE INDEX IF NOT EXISTS idx_call_logs_username ON call_logs(username);
  CREATE INDEX IF NOT EXISTS idx_sms_logs_username ON sms_logs(username);
`);

// User operations
export const createUser = db.prepare(`
  INSERT INTO users (username, public_key, created_at)
  VALUES (@username, @publicKey, @createdAt)
`);

export const getUserByUsername = db.prepare(`
  SELECT username, public_key as publicKey, created_at as createdAt
  FROM users WHERE username = ?
`);

export const getUserByPublicKey = db.prepare(`
  SELECT username, public_key as publicKey, created_at as createdAt
  FROM users WHERE public_key = ?
`);

// Key bundle operations
export const upsertKeyBundle = db.prepare(`
  INSERT OR REPLACE INTO key_bundles (username, identity_key, signed_prekey, signed_prekey_signature, updated_at)
  VALUES (@username, @identityKey, @signedPreKey, @signedPreKeySignature, @updatedAt)
`);

export const getKeyBundle = db.prepare(`
  SELECT identity_key as identityKey, signed_prekey as signedPreKey,
         signed_prekey_signature as signedPreKeySignature
  FROM key_bundles WHERE username = ?
`);

// One-time prekeys
export const addOneTimePreKeys = db.prepare(`
  INSERT INTO one_time_prekeys (username, prekey) VALUES (@username, @prekey)
`);

export const getAndConsumeOneTimePreKey = db.prepare(`
  UPDATE one_time_prekeys
  SET used = 1
  WHERE id = (
    SELECT id FROM one_time_prekeys
    WHERE username = ? AND used = 0
    ORDER BY id LIMIT 1
  )
  RETURNING prekey
`);

export const getUnusedPreKeyCount = db.prepare(`
  SELECT COUNT(*) as count FROM one_time_prekeys WHERE username = ? AND used = 0
`);

// Message operations
export const saveMessage = db.prepare(`
  INSERT INTO messages (id, sender_id, recipient_id, ciphertext, nonce, ephemeral_key, message_type, timestamp)
  VALUES (@id, @senderId, @recipientId, @ciphertext, @nonce, @ephemeralKey, @type, @timestamp)
`);

export const getUndeliveredMessages = db.prepare(`
  SELECT id, sender_id as senderId, recipient_id as recipientId,
         ciphertext, nonce, ephemeral_key as ephemeralKey,
         message_type as type, timestamp
  FROM messages
  WHERE recipient_id = ? AND delivered = 0
  ORDER BY timestamp ASC
`);

export const markMessagesDelivered = db.prepare(`
  UPDATE messages SET delivered = 1 WHERE recipient_id = ? AND delivered = 0
`);

export const getMessagesSince = db.prepare(`
  SELECT id, sender_id as senderId, recipient_id as recipientId,
         ciphertext, nonce, ephemeral_key as ephemeralKey,
         message_type as type, timestamp
  FROM messages
  WHERE recipient_id = ? AND timestamp > ?
  ORDER BY timestamp ASC
`);

// Challenge operations (for login)
export const createChallenge = db.prepare(`
  INSERT OR REPLACE INTO challenges (username, challenge, created_at, expires_at)
  VALUES (@username, @challenge, @createdAt, @expiresAt)
`);

export const getChallenge = db.prepare(`
  SELECT challenge, expires_at as expiresAt FROM challenges WHERE username = ?
`);

export const deleteChallenge = db.prepare(`
  DELETE FROM challenges WHERE username = ?
`);

// WebAuthn credential operations
export const saveWebAuthnCredential = db.prepare(`
  INSERT INTO webauthn_credentials (id, username, credential_id, credential_public_key, counter, credential_device_type, credential_backed_up, transports, name, created_at)
  VALUES (@id, @username, @credentialId, @credentialPublicKey, @counter, @credentialDeviceType, @credentialBackedUp, @transports, @name, @createdAt)
`);

export const getWebAuthnCredentialsByUsername = db.prepare(`
  SELECT id, credential_id as credentialId, credential_public_key as credentialPublicKey,
         counter, credential_device_type as credentialDeviceType,
         credential_backed_up as credentialBackedUp, transports, name, created_at as createdAt
  FROM webauthn_credentials WHERE username = ?
`);

export const getWebAuthnCredentialByCredentialId = db.prepare(`
  SELECT id, username, credential_id as credentialId, credential_public_key as credentialPublicKey,
         counter, credential_device_type as credentialDeviceType,
         credential_backed_up as credentialBackedUp, transports, name
  FROM webauthn_credentials WHERE credential_id = ?
`);

export const updateWebAuthnCounter = db.prepare(`
  UPDATE webauthn_credentials SET counter = @counter WHERE credential_id = @credentialId
`);

export const deleteWebAuthnCredential = db.prepare(`
  DELETE FROM webauthn_credentials WHERE id = ? AND username = ?
`);

// Trezor key operations
export const saveTrezorKey = db.prepare(`
  INSERT INTO trezor_keys (id, username, public_key, address, name, created_at)
  VALUES (@id, @username, @publicKey, @address, @name, @createdAt)
`);

export const getTrezorKeysByUsername = db.prepare(`
  SELECT id, public_key as publicKey, address, name, created_at as createdAt
  FROM trezor_keys WHERE username = ?
`);

export const getTrezorKeyByPublicKey = db.prepare(`
  SELECT id, username, public_key as publicKey, address, name
  FROM trezor_keys WHERE public_key = ?
`);

export const getTrezorKeyByAddress = db.prepare(`
  SELECT id, username, public_key as publicKey, address, name
  FROM trezor_keys WHERE address = ?
`);

export const deleteTrezorKey = db.prepare(`
  DELETE FROM trezor_keys WHERE id = ? AND username = ?
`);

// Get all hardware keys for a user
export const getHardwareKeyCount = db.prepare(`
  SELECT
    (SELECT COUNT(*) FROM webauthn_credentials WHERE username = ?) +
    (SELECT COUNT(*) FROM trezor_keys WHERE username = ?) as count
`);

// Phone credits operations
export const getPhoneCredits = db.prepare(`
  SELECT balance_cents as balanceCents, updated_at as updatedAt
  FROM phone_credits WHERE username = ?
`);

export const upsertPhoneCredits = db.prepare(`
  INSERT INTO phone_credits (username, balance_cents, updated_at)
  VALUES (@username, @balanceCents, @updatedAt)
  ON CONFLICT(username) DO UPDATE SET
    balance_cents = @balanceCents,
    updated_at = @updatedAt
`);

export const deductCredits = db.prepare(`
  UPDATE phone_credits
  SET balance_cents = balance_cents - @amount, updated_at = @updatedAt
  WHERE username = @username AND balance_cents >= @amount
`);

export const addCredits = db.prepare(`
  INSERT INTO phone_credits (username, balance_cents, updated_at)
  VALUES (@username, @amount, @updatedAt)
  ON CONFLICT(username) DO UPDATE SET
    balance_cents = balance_cents + @amount,
    updated_at = @updatedAt
`);

// Call log operations
export const saveCallLog = db.prepare(`
  INSERT INTO call_logs (id, username, direction, phone_number, status, twilio_sid, started_at)
  VALUES (@id, @username, @direction, @phoneNumber, @status, @twilioSid, @startedAt)
`);

export const updateCallLog = db.prepare(`
  UPDATE call_logs SET
    status = @status,
    duration_seconds = @durationSeconds,
    cost_cents = @costCents,
    ended_at = @endedAt
  WHERE id = @id
`);

export const getCallLogsByUsername = db.prepare(`
  SELECT id, direction, phone_number as phoneNumber, status, duration_seconds as durationSeconds,
         cost_cents as costCents, started_at as startedAt, ended_at as endedAt
  FROM call_logs WHERE username = ? ORDER BY started_at DESC LIMIT 50
`);

export const getCallLogByTwilioSid = db.prepare(`
  SELECT id, username, direction, phone_number as phoneNumber, status
  FROM call_logs WHERE twilio_sid = ?
`);

// SMS log operations
export const saveSmsLog = db.prepare(`
  INSERT INTO sms_logs (id, username, direction, phone_number, body, status, twilio_sid, created_at)
  VALUES (@id, @username, @direction, @phoneNumber, @body, @status, @twilioSid, @createdAt)
`);

export const updateSmsLog = db.prepare(`
  UPDATE sms_logs SET status = @status, cost_cents = @costCents WHERE id = @id
`);

export const getSmsLogsByUsername = db.prepare(`
  SELECT id, direction, phone_number as phoneNumber, body, status, cost_cents as costCents, created_at as createdAt
  FROM sms_logs WHERE username = ? ORDER BY created_at DESC LIMIT 50
`);

export const getSmsLogByTwilioSid = db.prepare(`
  SELECT id, username, direction, phone_number as phoneNumber, status
  FROM sms_logs WHERE twilio_sid = ?
`);

// Transaction helper
export function transaction<T>(fn: () => T): T {
  return db.transaction(fn)();
}

export default db;
