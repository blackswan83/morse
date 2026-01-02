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

// Transaction helper
export function transaction<T>(fn: () => T): T {
  return db.transaction(fn)();
}

export default db;
