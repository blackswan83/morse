import { toBase64, fromBase64 } from './crypto';

const DB_NAME = 'morse_secure';
const DB_VERSION = 1;

interface StoredKeys {
  identityPublicKey: string;
  identityPrivateKey: string;
  signedPreKeyPublic: string;
  signedPreKeyPrivate: string;
  oneTimePreKeys: Array<{ public: string; private: string; used: boolean }>;
}

interface StoredContact {
  username: string;
  publicKey: string;
  sharedSecret?: string;
  verified: boolean;
  verifiedAt?: number;
  addedAt: number;
}

interface StoredMessage {
  id: string;
  contactUsername: string;
  content: string;
  timestamp: number;
  sent: boolean;
  delivered: boolean;
}

let db: IDBDatabase | null = null;

export async function initDatabase(): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      db = request.result;
      resolve();
    };

    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result;

      // Store for user's keys
      if (!database.objectStoreNames.contains('keys')) {
        database.createObjectStore('keys', { keyPath: 'id' });
      }

      // Store for contacts
      if (!database.objectStoreNames.contains('contacts')) {
        const contactStore = database.createObjectStore('contacts', { keyPath: 'username' });
        contactStore.createIndex('verified', 'verified');
      }

      // Store for messages
      if (!database.objectStoreNames.contains('messages')) {
        const messageStore = database.createObjectStore('messages', { keyPath: 'id' });
        messageStore.createIndex('contactUsername', 'contactUsername');
        messageStore.createIndex('timestamp', 'timestamp');
      }

      // Store for user profile
      if (!database.objectStoreNames.contains('profile')) {
        database.createObjectStore('profile', { keyPath: 'id' });
      }
    };
  });
}

function getStore(storeName: string, mode: IDBTransactionMode = 'readonly'): IDBObjectStore {
  if (!db) throw new Error('Database not initialized');
  const transaction = db.transaction(storeName, mode);
  return transaction.objectStore(storeName);
}

// Key storage
export async function saveKeys(keys: StoredKeys): Promise<void> {
  return new Promise((resolve, reject) => {
    const store = getStore('keys', 'readwrite');
    const request = store.put({ id: 'main', ...keys });
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

export async function getKeys(): Promise<StoredKeys | null> {
  return new Promise((resolve, reject) => {
    const store = getStore('keys');
    const request = store.get('main');
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const result = request.result;
      if (result) {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { id, ...keys } = result;
        resolve(keys as StoredKeys);
      } else {
        resolve(null);
      }
    };
  });
}

export async function clearKeys(): Promise<void> {
  return new Promise((resolve, reject) => {
    const store = getStore('keys', 'readwrite');
    const request = store.clear();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Profile storage
export async function saveProfile(username: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const store = getStore('profile', 'readwrite');
    const request = store.put({ id: 'main', username, createdAt: Date.now() });
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

export async function getProfile(): Promise<{ username: string; createdAt: number } | null> {
  return new Promise((resolve, reject) => {
    const store = getStore('profile');
    const request = store.get('main');
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const result = request.result;
      if (result) {
        resolve({ username: result.username, createdAt: result.createdAt });
      } else {
        resolve(null);
      }
    };
  });
}

export async function clearProfile(): Promise<void> {
  return new Promise((resolve, reject) => {
    const store = getStore('profile', 'readwrite');
    const request = store.clear();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Contact storage
export async function saveContact(contact: StoredContact): Promise<void> {
  return new Promise((resolve, reject) => {
    const store = getStore('contacts', 'readwrite');
    const request = store.put(contact);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

export async function getContact(username: string): Promise<StoredContact | null> {
  return new Promise((resolve, reject) => {
    const store = getStore('contacts');
    const request = store.get(username);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result || null);
  });
}

export async function getAllContacts(): Promise<StoredContact[]> {
  return new Promise((resolve, reject) => {
    const store = getStore('contacts');
    const request = store.getAll();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

export async function updateContactSharedSecret(username: string, sharedSecret: string): Promise<void> {
  const contact = await getContact(username);
  if (contact) {
    contact.sharedSecret = sharedSecret;
    await saveContact(contact);
  }
}

export async function markContactVerified(username: string): Promise<void> {
  const contact = await getContact(username);
  if (contact) {
    contact.verified = true;
    contact.verifiedAt = Date.now();
    await saveContact(contact);
  }
}

// Message storage
export async function saveMessage(message: StoredMessage): Promise<void> {
  return new Promise((resolve, reject) => {
    const store = getStore('messages', 'readwrite');
    const request = store.put(message);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

export async function getMessagesByContact(contactUsername: string): Promise<StoredMessage[]> {
  return new Promise((resolve, reject) => {
    const store = getStore('messages');
    const index = store.index('contactUsername');
    const request = index.getAll(contactUsername);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const messages = request.result.sort((a, b) => a.timestamp - b.timestamp);
      resolve(messages);
    };
  });
}

export async function getAllMessages(): Promise<StoredMessage[]> {
  return new Promise((resolve, reject) => {
    const store = getStore('messages');
    const request = store.getAll();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const messages = request.result.sort((a, b) => a.timestamp - b.timestamp);
      resolve(messages);
    };
  });
}

// Clear all data (for logout)
export async function clearAllData(): Promise<void> {
  await clearKeys();
  await clearProfile();

  await new Promise<void>((resolve, reject) => {
    const store = getStore('contacts', 'readwrite');
    const request = store.clear();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });

  await new Promise<void>((resolve, reject) => {
    const store = getStore('messages', 'readwrite');
    const request = store.clear();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Helper to serialize keys for storage
export function serializeKeysForStorage(
  identityPublicKey: Uint8Array,
  identityPrivateKey: Uint8Array,
  signedPreKeyPublic: Uint8Array,
  signedPreKeyPrivate: Uint8Array,
  oneTimePreKeys: Array<{ publicKey: Uint8Array; privateKey: Uint8Array }>
): StoredKeys {
  return {
    identityPublicKey: toBase64(identityPublicKey),
    identityPrivateKey: toBase64(identityPrivateKey),
    signedPreKeyPublic: toBase64(signedPreKeyPublic),
    signedPreKeyPrivate: toBase64(signedPreKeyPrivate),
    oneTimePreKeys: oneTimePreKeys.map(kp => ({
      public: toBase64(kp.publicKey),
      private: toBase64(kp.privateKey),
      used: false,
    })),
  };
}

// Helper to deserialize keys from storage
export function deserializeKeysFromStorage(keys: StoredKeys) {
  return {
    identityPublicKey: fromBase64(keys.identityPublicKey),
    identityPrivateKey: fromBase64(keys.identityPrivateKey),
    signedPreKeyPublic: fromBase64(keys.signedPreKeyPublic),
    signedPreKeyPrivate: fromBase64(keys.signedPreKeyPrivate),
    oneTimePreKeys: keys.oneTimePreKeys.map(kp => ({
      publicKey: fromBase64(kp.public),
      privateKey: fromBase64(kp.private),
      used: kp.used,
    })),
  };
}
