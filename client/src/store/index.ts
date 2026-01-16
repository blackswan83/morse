import { create } from 'zustand';
import { io, Socket } from 'socket.io-client';
import * as crypto from '../lib/crypto';
import * as storage from '../lib/storage';
import { config } from '../lib/config';
import { logger } from '../lib/logger';

interface Contact {
  username: string;
  publicKey: string;
  sharedSecret?: Uint8Array;
  verified: boolean;
  online: boolean;
  addedAt: number;
}

interface Message {
  id: string;
  contactUsername: string;
  content: string;
  timestamp: number;
  sent: boolean;
  delivered: boolean;
}

interface KeyBundle {
  identityKeyPair: crypto.IdentityKeyPair;
  signedPreKeyPair: { publicKey: Uint8Array; privateKey: Uint8Array };
  signedPreKeySignature: Uint8Array;
  oneTimePreKeyPairs: Array<{ publicKey: Uint8Array; privateKey: Uint8Array }>;
}

interface AppState {
  // Connection
  socket: Socket | null;
  connected: boolean;

  // Auth
  username: string | null;
  keyBundle: KeyBundle | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  recoveryPhrase: string | null;

  // Contacts
  contacts: Map<string, Contact>;
  selectedContact: string | null;

  // Messages
  messages: Message[];

  // Ultra Protocol
  ultraVerificationData: {
    myPayload: string | null;
    pendingVerification: string | null;
  };

  // Actions
  initialize: () => Promise<void>;
  register: (username: string) => Promise<{ success: boolean; recoveryPhrase?: string; error?: string }>;
  login: () => Promise<{ success: boolean; error?: string }>;
  loginWithHardwareKey: (sessionToken: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  addContact: (username: string) => Promise<{ success: boolean; error?: string }>;
  sendMessage: (recipientUsername: string, content: string) => Promise<void>;
  selectContact: (username: string | null) => void;
  generateUltraPayload: () => string | null;
  verifyUltraPayload: (payload: string) => Promise<{ success: boolean; username?: string; error?: string }>;
  clearError: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial state
  socket: null,
  connected: false,
  username: null,
  keyBundle: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  recoveryPhrase: null,
  contacts: new Map(),
  selectedContact: null,
  messages: [],
  ultraVerificationData: {
    myPayload: null,
    pendingVerification: null,
  },

  // Initialize app - check for existing session
  initialize: async () => {
    try {
      await crypto.ready;
      await storage.initDatabase();

      const profile = await storage.getProfile();
      const keys = await storage.getKeys();

      if (profile && keys) {
        // Restore session
        const deserializedKeys = storage.deserializeKeysFromStorage(keys);

        set({
          username: profile.username,
          keyBundle: {
            identityKeyPair: {
              publicKey: deserializedKeys.identityPublicKey,
              privateKey: deserializedKeys.identityPrivateKey,
            },
            signedPreKeyPair: {
              publicKey: deserializedKeys.signedPreKeyPublic,
              privateKey: deserializedKeys.signedPreKeyPrivate,
            },
            signedPreKeySignature: new Uint8Array(0), // Not needed for login
            oneTimePreKeyPairs: deserializedKeys.oneTimePreKeys,
          },
          isLoading: false,
        });

        // Auto-login
        const contacts = await storage.getAllContacts();
        const contactsMap = new Map<string, Contact>();
        contacts.forEach(c => {
          contactsMap.set(c.username, {
            username: c.username,
            publicKey: c.publicKey,
            sharedSecret: c.sharedSecret ? crypto.fromBase64(c.sharedSecret) : undefined,
            verified: c.verified,
            online: false,
            addedAt: c.addedAt,
          });
        });

        const messages = await storage.getAllMessages();

        set({ contacts: contactsMap, messages });

        await get().login();
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      logger.error('Failed to initialize', error);
      set({ isLoading: false, error: 'Failed to initialize application' });
    }
  },

  // Register new user
  register: async (username: string) => {
    try {
      set({ isLoading: true, error: null });

      // Generate key bundle
      const keyBundle = crypto.generateKeyBundle();
      const serializedBundle = crypto.serializeKeyBundle(keyBundle);
      const recoveryPhrase = crypto.generateRecoveryPhrase();

      // Connect socket
      const socket = io(config.wsUrl, {
        transports: ['websocket'],
      });

      return new Promise((resolve) => {
        socket.on('connect', () => {
          set({ socket, connected: true });

          // Register with server
          socket.emit('register', {
            username,
            publicKey: serializedBundle.identityKey,
            keyBundle: serializedBundle,
          });
        });

        socket.on('registered', async (data: { username: string; publicKey: string }) => {
          // Save to local storage
          const storedKeys = storage.serializeKeysForStorage(
            keyBundle.identityKeyPair.publicKey,
            keyBundle.identityKeyPair.privateKey,
            keyBundle.signedPreKeyPair.publicKey,
            keyBundle.signedPreKeyPair.privateKey,
            keyBundle.oneTimePreKeyPairs
          );
          await storage.saveKeys(storedKeys);
          await storage.saveProfile(username);

          set({
            username: data.username,
            keyBundle,
            isAuthenticated: true,
            isLoading: false,
            recoveryPhrase,
          });

          setupSocketListeners(socket, get, set);
          resolve({ success: true, recoveryPhrase });
        });

        socket.on('error', (error: { code: string; message: string }) => {
          set({ isLoading: false, error: error.message });
          socket.disconnect();
          resolve({ success: false, error: error.message });
        });

        socket.on('connect_error', () => {
          set({ isLoading: false, error: 'Failed to connect to server' });
          resolve({ success: false, error: 'Failed to connect to server' });
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Registration failed';
      set({ isLoading: false, error: message });
      return { success: false, error: message };
    }
  },

  // Login existing user
  login: async () => {
    const { username, keyBundle } = get();

    if (!username || !keyBundle) {
      return { success: false, error: 'No stored credentials' };
    }

    try {
      set({ isLoading: true, error: null });

      const socket = io(config.wsUrl, {
        transports: ['websocket'],
      });

      return new Promise((resolve) => {
        socket.on('connect', () => {
          set({ socket, connected: true });
          socket.emit('requestChallenge', username);
        });

        socket.on('challenge', (data: { challenge: string }) => {
          // Sign the challenge
          const challengeBytes = crypto.fromBase64(data.challenge);
          const signature = crypto.sign(challengeBytes, keyBundle.identityKeyPair.privateKey);

          socket.emit('login', {
            username,
            signature: crypto.toBase64(signature),
            challenge: data.challenge,
          });
        });

        socket.on('loggedIn', (_data: { username: string }) => {
          set({ isAuthenticated: true, isLoading: false });
          setupSocketListeners(socket, get, set);
          resolve({ success: true });
        });

        socket.on('error', (error: { code: string; message: string }) => {
          set({ isLoading: false, error: error.message });
          socket.disconnect();
          resolve({ success: false, error: error.message });
        });

        socket.on('connect_error', () => {
          set({ isLoading: false, error: 'Failed to connect to server' });
          resolve({ success: false, error: 'Failed to connect to server' });
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed';
      set({ isLoading: false, error: message });
      return { success: false, error: message };
    }
  },

  // Login with hardware key (WebAuthn or Trezor)
  loginWithHardwareKey: async (sessionToken: string) => {
    const { username } = get();

    if (!username) {
      return { success: false, error: 'No stored credentials' };
    }

    try {
      set({ isLoading: true, error: null });

      const socket = io(config.wsUrl, {
        transports: ['websocket'],
      });

      return new Promise((resolve) => {
        socket.on('connect', () => {
          set({ socket, connected: true });
          socket.emit('loginWithHardwareKey', { username, sessionToken });
        });

        socket.on('loggedIn', () => {
          set({ isAuthenticated: true, isLoading: false });
          setupSocketListeners(socket, get, set);
          resolve({ success: true });
        });

        socket.on('error', (error: { code: string; message: string }) => {
          set({ isLoading: false, error: error.message });
          socket.disconnect();
          resolve({ success: false, error: error.message });
        });

        socket.on('connect_error', () => {
          set({ isLoading: false, error: 'Failed to connect to server' });
          resolve({ success: false, error: 'Failed to connect to server' });
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Hardware key login failed';
      set({ isLoading: false, error: message });
      return { success: false, error: message };
    }
  },

  // Logout
  logout: async () => {
    const { socket } = get();
    if (socket) {
      socket.disconnect();
    }
    await storage.clearAllData();
    set({
      socket: null,
      connected: false,
      username: null,
      keyBundle: null,
      isAuthenticated: false,
      contacts: new Map(),
      messages: [],
      selectedContact: null,
      recoveryPhrase: null,
    });
  },

  // Add contact
  addContact: async (username: string) => {
    const { socket, contacts, keyBundle, username: myUsername } = get();

    if (!socket || !keyBundle || !myUsername) {
      return { success: false, error: 'Not connected' };
    }

    if (username === myUsername) {
      return { success: false, error: 'Cannot add yourself as a contact' };
    }

    if (contacts.has(username)) {
      return { success: false, error: 'Contact already exists' };
    }

    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        resolve({ success: false, error: 'Request timed out' });
      }, 10000);

      const handleKeyBundle = async (bundle: {
        username: string;
        identityKey: string;
        signedPreKey: string;
        signedPreKeySignature: string;
        oneTimePreKey?: string;
        isOnline?: boolean;
      }) => {
        if (bundle.username !== username) return;

        clearTimeout(timeout);
        socket.off('keyBundle', handleKeyBundle);

        try {
          // Verify signed prekey signature
          const identityKeyBytes = crypto.fromBase64(bundle.identityKey);
          const signedPreKeyBytes = crypto.fromBase64(bundle.signedPreKey);
          const signatureBytes = crypto.fromBase64(bundle.signedPreKeySignature);

          const isValid = crypto.verify(signatureBytes, signedPreKeyBytes, identityKeyBytes);
          if (!isValid) {
            resolve({ success: false, error: 'Invalid key bundle signature' });
            return;
          }

          // Generate ephemeral key for key exchange
          const ephemeralKeyPair = crypto.generateEphemeralKeyPair();

          // Derive shared secret
          const sharedSecret = crypto.deriveSharedSecret(
            keyBundle.identityKeyPair.privateKey,
            ephemeralKeyPair.privateKey,
            identityKeyBytes,
            signedPreKeyBytes,
            bundle.oneTimePreKey ? crypto.fromBase64(bundle.oneTimePreKey) : undefined
          );

          // Create contact
          const contact: Contact = {
            username: bundle.username,
            publicKey: bundle.identityKey,
            sharedSecret,
            verified: false,
            online: bundle.isOnline || false,
            addedAt: Date.now(),
          };

          // Save to storage
          await storage.saveContact({
            username: contact.username,
            publicKey: contact.publicKey,
            sharedSecret: crypto.toBase64(sharedSecret),
            verified: false,
            addedAt: contact.addedAt,
          });

          // Update state
          const newContacts = new Map(get().contacts);
          newContacts.set(username, contact);
          set({ contacts: newContacts });

          // Send initial key exchange message
          const keyExchangePayload = JSON.stringify({
            type: 'key_exchange',
            ephemeralKey: crypto.toBase64(ephemeralKeyPair.publicKey),
          });

          const { ciphertext, nonce } = crypto.encrypt(keyExchangePayload, sharedSecret);

          socket.emit('sendMessage', {
            senderId: myUsername,
            recipientId: username,
            ciphertext: crypto.toBase64(ciphertext),
            nonce: crypto.toBase64(nonce),
            ephemeralKey: crypto.toBase64(ephemeralKeyPair.publicKey),
            type: 'key_exchange',
          });

          resolve({ success: true });
        } catch (error) {
          logger.error('Failed to process key bundle', error);
          resolve({ success: false, error: 'Failed to establish secure connection' });
        }
      };

      socket.on('keyBundle', handleKeyBundle);
      socket.emit('getKeyBundle', username);
    });
  },

  // Send message
  sendMessage: async (recipientUsername: string, content: string) => {
    const { socket, contacts, keyBundle, username, messages } = get();

    if (!socket || !keyBundle || !username) {
      throw new Error('Not connected');
    }

    const contact = contacts.get(recipientUsername);
    if (!contact || !contact.sharedSecret) {
      throw new Error('No secure channel established with this contact');
    }

    const { ciphertext, nonce } = crypto.encrypt(content, contact.sharedSecret);
    const messageId = crypto.toBase64(crypto.generateNonce()).slice(0, 16);

    const message: Message = {
      id: messageId,
      contactUsername: recipientUsername,
      content,
      timestamp: Date.now(),
      sent: true,
      delivered: false,
    };

    // Save locally
    await storage.saveMessage(message);
    set({ messages: [...messages, message] });

    // Send to server
    socket.emit('sendMessage', {
      senderId: username,
      recipientId: recipientUsername,
      ciphertext: crypto.toBase64(ciphertext),
      nonce: crypto.toBase64(nonce),
      type: 'text',
    });
  },

  // Select contact for chat
  selectContact: (username: string | null) => {
    set({ selectedContact: username });
  },

  // Generate Ultra Protocol verification payload
  generateUltraPayload: () => {
    const { username, keyBundle } = get();

    if (!username || !keyBundle) {
      return null;
    }

    const ephemeralKeyPair = crypto.generateEphemeralKeyPair();
    const nonce = crypto.toBase64(crypto.generateNonce());
    const timestamp = Date.now();

    const payload = {
      protocol: 'ultra/1.0',
      username,
      identityKey: crypto.toBase64(keyBundle.identityKeyPair.publicKey),
      ephemeralKey: crypto.toBase64(ephemeralKeyPair.publicKey),
      timestamp,
      nonce,
    };

    const payloadString = JSON.stringify(payload);
    set({
      ultraVerificationData: {
        ...get().ultraVerificationData,
        myPayload: payloadString,
      },
    });

    return payloadString;
  },

  // Verify Ultra Protocol payload from QR scan
  verifyUltraPayload: async (payloadString: string) => {
    const { contacts, keyBundle, username: myUsername } = get();

    if (!keyBundle || !myUsername) {
      return { success: false, error: 'Not authenticated' };
    }

    try {
      const payload = JSON.parse(payloadString);

      if (payload.protocol !== 'ultra/1.0') {
        return { success: false, error: 'Invalid Ultra Protocol version' };
      }

      // Check timestamp (allow 5 minute window)
      const now = Date.now();
      if (Math.abs(now - payload.timestamp) > 5 * 60 * 1000) {
        return { success: false, error: 'Verification payload expired' };
      }

      // Check if contact exists
      const existingContact = contacts.get(payload.username);

      if (existingContact) {
        // Verify the key matches
        if (existingContact.publicKey !== payload.identityKey) {
          return { success: false, error: 'Key mismatch - possible impersonation attempt!' };
        }

        // Mark as verified
        await storage.markContactVerified(payload.username);

        const newContacts = new Map(contacts);
        newContacts.set(payload.username, {
          ...existingContact,
          verified: true,
        });
        set({ contacts: newContacts });

        return { success: true, username: payload.username };
      } else {
        // Add as new verified contact
        const result = await get().addContact(payload.username);
        if (result.success) {
          await storage.markContactVerified(payload.username);

          const newContacts = new Map(get().contacts);
          const contact = newContacts.get(payload.username);
          if (contact) {
            newContacts.set(payload.username, { ...contact, verified: true });
            set({ contacts: newContacts });
          }
        }
        return { success: true, username: payload.username };
      }
    } catch (error) {
      logger.error('Failed to verify Ultra payload', error);
      return { success: false, error: 'Invalid verification data' };
    }
  },

  clearError: () => set({ error: null }),
}));

// Socket event listeners setup
function setupSocketListeners(
  socket: Socket,
  get: () => AppState,
  set: (state: Partial<AppState>) => void
) {
  socket.on('message', async (msg: {
    id: string;
    senderId: string;
    recipientId: string;
    ciphertext: string;
    nonce: string;
    ephemeralKey?: string;
    type: 'text' | 'key_exchange' | 'ultra_verify';
    timestamp: number;
  }) => {
    const { contacts, messages, keyBundle } = get();

    if (!keyBundle) return;

    const contact = contacts.get(msg.senderId);

    if (msg.type === 'key_exchange' && msg.ephemeralKey) {
      // Handle incoming key exchange
      try {
        // Validate the ephemeral key format
        crypto.fromBase64(msg.ephemeralKey);

        // We need to get their identity key from the server or the message
        // For now, request their key bundle if we don't have them as a contact
        if (!contact) {
          socket.emit('addContact', msg.senderId);
        }
      } catch (error) {
        logger.error('Failed to process key exchange', error);
      }
      return;
    }

    if (!contact || !contact.sharedSecret) {
      logger.warn('Received message from unknown contact or no shared secret', { senderId: msg.senderId });
      return;
    }

    try {
      const ciphertext = crypto.fromBase64(msg.ciphertext);
      const nonce = crypto.fromBase64(msg.nonce);
      const decrypted = crypto.decrypt(ciphertext, nonce, contact.sharedSecret);

      const message: Message = {
        id: msg.id,
        contactUsername: msg.senderId,
        content: decrypted,
        timestamp: msg.timestamp,
        sent: false,
        delivered: true,
      };

      await storage.saveMessage(message);
      set({ messages: [...messages, message] });
    } catch (error) {
      logger.error('Failed to decrypt message', error);
    }
  });

  socket.on('userOnline', (username: string) => {
    const { contacts } = get();
    const contact = contacts.get(username);
    if (contact) {
      const newContacts = new Map(contacts);
      newContacts.set(username, { ...contact, online: true });
      set({ contacts: newContacts });
    }
  });

  socket.on('userOffline', (username: string) => {
    const { contacts } = get();
    const contact = contacts.get(username);
    if (contact) {
      const newContacts = new Map(contacts);
      newContacts.set(username, { ...contact, online: false });
      set({ contacts: newContacts });
    }
  });

  socket.on('contactAdded', async (data: { username: string; publicKey: string }) => {
    // This is triggered when we request someone's key after receiving a key_exchange message
    const { contacts } = get();

    if (!contacts.has(data.username)) {
      // This is handled by addContact flow
    }
  });

  socket.on('messageSent', (_data: { id: string; timestamp: number }) => {
    // Could update message delivery status here
  });

  socket.on('disconnect', () => {
    set({ connected: false });
  });

  socket.on('connect', () => {
    set({ connected: true });
  });
}
