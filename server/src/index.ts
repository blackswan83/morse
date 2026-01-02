import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import cors from 'cors';
import sodium from 'libsodium-wrappers';
import { v4 as uuidv4 } from 'uuid';
import {
  createUser,
  getUserByUsername,
  upsertKeyBundle,
  getKeyBundle,
  addOneTimePreKeys,
  getAndConsumeOneTimePreKey,
  saveMessage,
  getUndeliveredMessages,
  markMessagesDelivered,
  createChallenge,
  getChallenge,
  deleteChallenge,
  transaction,
} from './db.js';

const app = express();
const httpServer = createServer(app);

// Initialize Socket.io with CORS
const io = new Server(httpServer, {
  cors: {
    origin: ['http://localhost:5173', 'http://localhost:3000'],
    methods: ['GET', 'POST'],
  },
});

app.use(cors());
app.use(express.json());

// Track online users
const onlineUsers = new Map<string, string>(); // username -> socketId

// Wait for libsodium to be ready
await sodium.ready;

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: Date.now() });
});

// Get user public key (REST endpoint for key transparency)
app.get('/api/users/:username/key', (req, res) => {
  const { username } = req.params;
  const user = getUserByUsername.get(username) as { publicKey: string } | undefined;

  if (!user) {
    res.status(404).json({ error: 'User not found' });
    return;
  }

  res.json({ username, publicKey: user.publicKey });
});

// Socket.io connection handling
io.on('connection', (socket) => {
  console.log(`Client connected: ${socket.id}`);
  let authenticatedUser: string | null = null;

  // Request login challenge
  socket.on('requestChallenge', (username: string) => {
    const user = getUserByUsername.get(username);
    if (!user) {
      socket.emit('error', { code: 'USER_NOT_FOUND', message: 'User not found' });
      return;
    }

    const challenge = sodium.to_base64(sodium.randombytes_buf(32));
    const now = Math.floor(Date.now() / 1000);

    createChallenge.run({
      username,
      challenge,
      createdAt: now,
      expiresAt: now + 300, // 5 minutes
    });

    socket.emit('challenge', { challenge });
  });

  // Register new user
  socket.on('register', (data: {
    username: string;
    publicKey: string;
    keyBundle: {
      identityKey: string;
      signedPreKey: string;
      signedPreKeySignature: string;
      oneTimePreKeys: string[];
    };
  }) => {
    try {
      const { username, publicKey, keyBundle } = data;

      // Validate username format
      if (!/^[a-zA-Z0-9_]{3,32}$/.test(username)) {
        socket.emit('error', { code: 'INVALID_USERNAME', message: 'Username must be 3-32 alphanumeric characters or underscores' });
        return;
      }

      // Check if username exists
      if (getUserByUsername.get(username)) {
        socket.emit('error', { code: 'USERNAME_TAKEN', message: 'Username already exists' });
        return;
      }

      // Verify the identity key matches the public key
      if (publicKey !== keyBundle.identityKey) {
        socket.emit('error', { code: 'KEY_MISMATCH', message: 'Public key must match identity key' });
        return;
      }

      // Verify signed prekey signature
      try {
        const publicKeyBytes = sodium.from_base64(publicKey);
        const signedPreKeyBytes = sodium.from_base64(keyBundle.signedPreKey);
        const signatureBytes = sodium.from_base64(keyBundle.signedPreKeySignature);

        const isValid = sodium.crypto_sign_verify_detached(
          signatureBytes,
          signedPreKeyBytes,
          publicKeyBytes
        );

        if (!isValid) {
          socket.emit('error', { code: 'INVALID_SIGNATURE', message: 'Signed prekey signature is invalid' });
          return;
        }
      } catch (e) {
        socket.emit('error', { code: 'CRYPTO_ERROR', message: 'Failed to verify signature' });
        return;
      }

      // Create user in transaction
      transaction(() => {
        const now = Date.now();
        createUser.run({ username, publicKey, createdAt: now });

        upsertKeyBundle.run({
          username,
          identityKey: keyBundle.identityKey,
          signedPreKey: keyBundle.signedPreKey,
          signedPreKeySignature: keyBundle.signedPreKeySignature,
          updatedAt: now,
        });

        // Add one-time prekeys
        for (const prekey of keyBundle.oneTimePreKeys) {
          addOneTimePreKeys.run({ username, prekey });
        }
      });

      authenticatedUser = username;
      onlineUsers.set(username, socket.id);

      socket.emit('registered', { username, publicKey });
      socket.broadcast.emit('userOnline', username);

      console.log(`User registered: ${username}`);
    } catch (error) {
      console.error('Registration error:', error);
      socket.emit('error', { code: 'REGISTRATION_FAILED', message: 'Failed to register user' });
    }
  });

  // Login with signature
  socket.on('login', (data: { username: string; signature: string; challenge: string }) => {
    try {
      const { username, signature, challenge } = data;

      const user = getUserByUsername.get(username) as { publicKey: string } | undefined;
      if (!user) {
        socket.emit('error', { code: 'USER_NOT_FOUND', message: 'User not found' });
        return;
      }

      const storedChallenge = getChallenge.get(username) as { challenge: string; expiresAt: number } | undefined;
      if (!storedChallenge || storedChallenge.challenge !== challenge) {
        socket.emit('error', { code: 'INVALID_CHALLENGE', message: 'Invalid or expired challenge' });
        return;
      }

      if (storedChallenge.expiresAt < Math.floor(Date.now() / 1000)) {
        deleteChallenge.run(username);
        socket.emit('error', { code: 'CHALLENGE_EXPIRED', message: 'Challenge has expired' });
        return;
      }

      // Verify signature
      const publicKeyBytes = sodium.from_base64(user.publicKey);
      const signatureBytes = sodium.from_base64(signature);
      const challengeBytes = sodium.from_base64(challenge);

      const isValid = sodium.crypto_sign_verify_detached(signatureBytes, challengeBytes, publicKeyBytes);

      if (!isValid) {
        socket.emit('error', { code: 'INVALID_SIGNATURE', message: 'Invalid signature' });
        return;
      }

      deleteChallenge.run(username);
      authenticatedUser = username;
      onlineUsers.set(username, socket.id);

      socket.emit('loggedIn', { username, publicKey: user.publicKey });
      socket.broadcast.emit('userOnline', username);

      // Send undelivered messages
      const messages = getUndeliveredMessages.all(username);
      if (messages.length > 0) {
        for (const msg of messages) {
          socket.emit('message', msg);
        }
        markMessagesDelivered.run(username);
      }

      console.log(`User logged in: ${username}`);
    } catch (error) {
      console.error('Login error:', error);
      socket.emit('error', { code: 'LOGIN_FAILED', message: 'Failed to login' });
    }
  });

  // Get key bundle for a user (for key exchange)
  socket.on('getKeyBundle', (username: string) => {
    if (!authenticatedUser) {
      socket.emit('error', { code: 'UNAUTHORIZED', message: 'Not authenticated' });
      return;
    }

    const bundle = getKeyBundle.get(username) as {
      identityKey: string;
      signedPreKey: string;
      signedPreKeySignature: string;
    } | undefined;

    if (!bundle) {
      socket.emit('error', { code: 'USER_NOT_FOUND', message: 'User not found' });
      return;
    }

    // Try to get a one-time prekey
    const otpResult = getAndConsumeOneTimePreKey.get(username) as { prekey: string } | undefined;

    socket.emit('keyBundle', {
      username,
      identityKey: bundle.identityKey,
      signedPreKey: bundle.signedPreKey,
      signedPreKeySignature: bundle.signedPreKeySignature,
      oneTimePreKey: otpResult?.prekey || null,
    });
  });

  // Send encrypted message
  socket.on('sendMessage', (msg: {
    senderId: string;
    recipientId: string;
    ciphertext: string;
    nonce: string;
    ephemeralKey?: string;
    type: 'text' | 'key_exchange' | 'ultra_verify';
  }) => {
    if (!authenticatedUser || authenticatedUser !== msg.senderId) {
      socket.emit('error', { code: 'UNAUTHORIZED', message: 'Not authenticated' });
      return;
    }

    const messageId = uuidv4();
    const timestamp = Date.now();

    const fullMessage = {
      id: messageId,
      senderId: msg.senderId,
      recipientId: msg.recipientId,
      ciphertext: msg.ciphertext,
      nonce: msg.nonce,
      ephemeralKey: msg.ephemeralKey || null,
      type: msg.type,
      timestamp,
    };

    // Save to database
    saveMessage.run(fullMessage);

    // Try to deliver in real-time
    const recipientSocketId = onlineUsers.get(msg.recipientId);
    if (recipientSocketId) {
      io.to(recipientSocketId).emit('message', fullMessage);
      markMessagesDelivered.run(msg.recipientId);
    }

    // Confirm to sender
    socket.emit('messageSent', { id: messageId, timestamp });
  });

  // Add contact (get their public key)
  socket.on('addContact', (username: string) => {
    if (!authenticatedUser) {
      socket.emit('error', { code: 'UNAUTHORIZED', message: 'Not authenticated' });
      return;
    }

    const user = getUserByUsername.get(username) as { username: string; publicKey: string } | undefined;
    if (!user) {
      socket.emit('error', { code: 'USER_NOT_FOUND', message: 'User not found' });
      return;
    }

    socket.emit('contactAdded', { username: user.username, publicKey: user.publicKey });
  });

  // Get messages since timestamp
  socket.on('getMessages', (since?: number) => {
    if (!authenticatedUser) {
      socket.emit('error', { code: 'UNAUTHORIZED', message: 'Not authenticated' });
      return;
    }

    const messages = getUndeliveredMessages.all(authenticatedUser);
    socket.emit('messages', messages);
  });

  // Handle disconnect
  socket.on('disconnect', () => {
    if (authenticatedUser) {
      onlineUsers.delete(authenticatedUser);
      socket.broadcast.emit('userOffline', authenticatedUser);
      console.log(`User disconnected: ${authenticatedUser}`);
    }
    console.log(`Client disconnected: ${socket.id}`);
  });
});

const PORT = process.env.PORT || 3001;

httpServer.listen(PORT, () => {
  console.log(`Morse server running on port ${PORT}`);
  console.log(`WebSocket endpoint: ws://localhost:${PORT}`);
});
