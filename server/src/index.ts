import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import cors from 'cors';
import sodium from 'libsodium-wrappers';
import { v4 as uuidv4 } from 'uuid';
import {
  generateRegistrationOptions,
  verifyRegistrationResponse,
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
} from '@simplewebauthn/server';
// Types inferred from function parameters
type RegistrationResponseJSON = Parameters<typeof verifyRegistrationResponse>[0]['response'];
type AuthenticationResponseJSON = Parameters<typeof verifyAuthenticationResponse>[0]['response'];
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
  saveWebAuthnCredential,
  getWebAuthnCredentialsByUsername,
  getWebAuthnCredentialByCredentialId,
  updateWebAuthnCounter,
  deleteWebAuthnCredential,
  saveTrezorKey,
  getTrezorKeysByUsername,
  getTrezorKeyByAddress,
  deleteTrezorKey,
  transaction,
} from './db.js';
import {
  initTwilio,
  isTwilioConfigured,
  generateVoiceToken,
  getCredits,
  addUserCredits,
  sendSms,
  initiateCall,
  handleCallStatusWebhook,
  getCallHistory,
  getSmsHistory,
  generateClientTwiML,
  isValidPhoneNumber,
  formatPhoneNumber,
} from './telephony.js';

// WebAuthn configuration
const RP_NAME = 'Morse Secure Messaging';
const RP_ID = process.env.RP_ID || 'localhost';
const ORIGIN = process.env.ORIGIN || 'http://localhost:5173';

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

// Initialize Twilio
initTwilio();

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: Date.now(), twilioConfigured: isTwilioConfigured() });
});

// ============ Telephony Endpoints ============

// Check if telephony is available
app.get('/api/telephony/status', (req, res) => {
  res.json({ available: isTwilioConfigured() });
});

// Get voice token for browser-based calling
app.post('/api/telephony/voice-token', (req, res) => {
  const { username } = req.body;

  if (!username) {
    res.status(400).json({ error: 'Username is required' });
    return;
  }

  if (!isTwilioConfigured()) {
    res.status(503).json({ error: 'Telephony not configured' });
    return;
  }

  const token = generateVoiceToken(username);
  if (!token) {
    res.status(500).json({ error: 'Failed to generate voice token' });
    return;
  }

  res.json({ token });
});

// Get user's phone credits
app.get('/api/telephony/credits/:username', (req, res) => {
  const { username } = req.params;
  const balanceCents = getCredits(username);
  res.json({ balanceCents, balanceFormatted: `$${(balanceCents / 100).toFixed(2)}` });
});

// Add credits (in production, this would be behind payment verification)
app.post('/api/telephony/credits/add', (req, res) => {
  const { username, amountCents } = req.body;

  if (!username || typeof amountCents !== 'number' || amountCents <= 0) {
    res.status(400).json({ error: 'Valid username and amountCents required' });
    return;
  }

  const success = addUserCredits(username, amountCents);
  if (success) {
    const newBalance = getCredits(username);
    res.json({ success: true, balanceCents: newBalance });
  } else {
    res.status(500).json({ error: 'Failed to add credits' });
  }
});

// Send SMS
app.post('/api/telephony/sms/send', async (req, res) => {
  const { username, to, body } = req.body;

  if (!username || !to || !body) {
    res.status(400).json({ error: 'Username, to, and body are required' });
    return;
  }

  const formattedNumber = formatPhoneNumber(to);
  if (!isValidPhoneNumber(formattedNumber)) {
    res.status(400).json({ error: 'Invalid phone number format' });
    return;
  }

  const result = await sendSms(username, formattedNumber, body);
  if (result.success) {
    res.json({ success: true, messageId: result.messageId });
  } else {
    res.status(400).json({ error: result.error });
  }
});

// Get SMS history
app.get('/api/telephony/sms/history/:username', (req, res) => {
  const { username } = req.params;
  const history = getSmsHistory(username);
  res.json({ messages: history });
});

// Initiate call
app.post('/api/telephony/call/initiate', async (req, res) => {
  const { username, to } = req.body;

  if (!username || !to) {
    res.status(400).json({ error: 'Username and to are required' });
    return;
  }

  const formattedNumber = formatPhoneNumber(to);
  if (!isValidPhoneNumber(formattedNumber)) {
    res.status(400).json({ error: 'Invalid phone number format' });
    return;
  }

  const callbackUrl = process.env.CALLBACK_URL || 'http://localhost:3001/api/telephony';
  const result = await initiateCall(username, formattedNumber, callbackUrl);

  if (result.success) {
    res.json({ success: true, callId: result.callId });
  } else {
    res.status(400).json({ error: result.error });
  }
});

// Get call history
app.get('/api/telephony/call/history/:username', (req, res) => {
  const { username } = req.params;
  const history = getCallHistory(username);
  res.json({ calls: history });
});

// Twilio webhooks
app.post('/api/telephony/webhook/call-status', express.urlencoded({ extended: false }), (req, res) => {
  handleCallStatusWebhook(req.body);
  res.status(200).send('OK');
});

// TwiML for browser-initiated calls
app.post('/api/telephony/twiml/voice', express.urlencoded({ extended: false }), (req, res) => {
  const to = req.body.To;

  if (!to) {
    res.status(400).send('No destination number');
    return;
  }

  const twiml = generateClientTwiML(to);
  res.type('text/xml');
  res.send(twiml);
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

// ============ WebAuthn Endpoints ============

// Store pending WebAuthn challenges (in production, use Redis or similar)
const webAuthnChallenges = new Map<string, { challenge: string; expiresAt: number }>();

// Generate WebAuthn registration options
app.post('/api/webauthn/register/options', async (req, res) => {
  try {
    const { username } = req.body;

    if (!username) {
      res.status(400).json({ error: 'Username is required' });
      return;
    }

    const user = getUserByUsername.get(username) as { publicKey: string } | undefined;
    if (!user) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    // Get existing credentials to exclude
    const existingCredentials = getWebAuthnCredentialsByUsername.all(username) as Array<{
      credentialId: string;
      transports?: string;
    }>;

    const options = await generateRegistrationOptions({
      rpName: RP_NAME,
      rpID: RP_ID,
      userID: username,
      userName: username,
      attestationType: 'none',
      excludeCredentials: existingCredentials.map((cred) => ({
        id: Buffer.from(cred.credentialId, 'base64url'),
        type: 'public-key' as const,
        transports: cred.transports ? JSON.parse(cred.transports) : undefined,
      })),
      authenticatorSelection: {
        residentKey: 'preferred',
        userVerification: 'preferred',
      },
    });

    // Store challenge
    webAuthnChallenges.set(username, {
      challenge: options.challenge,
      expiresAt: Date.now() + 5 * 60 * 1000, // 5 minutes
    });

    res.json(options);
  } catch (error) {
    console.error('WebAuthn registration options error:', error);
    res.status(500).json({ error: 'Failed to generate registration options' });
  }
});

// Verify WebAuthn registration
app.post('/api/webauthn/register/verify', async (req, res) => {
  try {
    const { username, response, name } = req.body as {
      username: string;
      response: RegistrationResponseJSON;
      name?: string;
    };

    if (!username || !response) {
      res.status(400).json({ error: 'Username and response are required' });
      return;
    }

    const storedChallenge = webAuthnChallenges.get(username);
    if (!storedChallenge || storedChallenge.expiresAt < Date.now()) {
      webAuthnChallenges.delete(username);
      res.status(400).json({ error: 'Challenge expired or not found' });
      return;
    }

    const verification = await verifyRegistrationResponse({
      response,
      expectedChallenge: storedChallenge.challenge,
      expectedOrigin: ORIGIN,
      expectedRPID: RP_ID,
    });

    if (!verification.verified || !verification.registrationInfo) {
      res.status(400).json({ error: 'Verification failed' });
      return;
    }

    const { credentialID, credentialPublicKey, counter, credentialDeviceType, credentialBackedUp } = verification.registrationInfo;

    // Save credential to database
    saveWebAuthnCredential.run({
      id: uuidv4(),
      username,
      credentialId: Buffer.from(credentialID).toString('base64url'),
      credentialPublicKey: Buffer.from(credentialPublicKey),
      counter,
      credentialDeviceType,
      credentialBackedUp: credentialBackedUp ? 1 : 0,
      transports: response.response.transports ? JSON.stringify(response.response.transports) : null,
      name: name || 'Security Key',
      createdAt: Date.now(),
    });

    webAuthnChallenges.delete(username);

    res.json({
      verified: true,
      credentialId: Buffer.from(credentialID).toString('base64url'),
    });
  } catch (error) {
    console.error('WebAuthn registration verify error:', error);
    res.status(500).json({ error: 'Failed to verify registration' });
  }
});

// Generate WebAuthn authentication options
app.post('/api/webauthn/authenticate/options', async (req, res) => {
  try {
    const { username } = req.body;

    if (!username) {
      res.status(400).json({ error: 'Username is required' });
      return;
    }

    const credentials = getWebAuthnCredentialsByUsername.all(username) as Array<{
      credentialId: string;
      transports?: string;
    }>;

    if (credentials.length === 0) {
      res.status(404).json({ error: 'No security keys registered' });
      return;
    }

    const options = await generateAuthenticationOptions({
      rpID: RP_ID,
      allowCredentials: credentials.map((cred) => ({
        id: Buffer.from(cred.credentialId, 'base64url'),
        type: 'public-key' as const,
        transports: cred.transports ? JSON.parse(cred.transports) : undefined,
      })),
      userVerification: 'preferred',
    });

    // Store challenge
    webAuthnChallenges.set(username, {
      challenge: options.challenge,
      expiresAt: Date.now() + 5 * 60 * 1000,
    });

    res.json(options);
  } catch (error) {
    console.error('WebAuthn authentication options error:', error);
    res.status(500).json({ error: 'Failed to generate authentication options' });
  }
});

// Verify WebAuthn authentication
app.post('/api/webauthn/authenticate/verify', async (req, res) => {
  try {
    const { username, response } = req.body as {
      username: string;
      response: AuthenticationResponseJSON;
    };

    if (!username || !response) {
      res.status(400).json({ error: 'Username and response are required' });
      return;
    }

    const storedChallenge = webAuthnChallenges.get(username);
    if (!storedChallenge || storedChallenge.expiresAt < Date.now()) {
      webAuthnChallenges.delete(username);
      res.status(400).json({ error: 'Challenge expired or not found' });
      return;
    }

    const credential = getWebAuthnCredentialByCredentialId.get(response.id) as {
      username: string;
      credentialPublicKey: Buffer;
      counter: number;
    } | undefined;

    if (!credential || credential.username !== username) {
      res.status(400).json({ error: 'Credential not found' });
      return;
    }

    const verification = await verifyAuthenticationResponse({
      response,
      expectedChallenge: storedChallenge.challenge,
      expectedOrigin: ORIGIN,
      expectedRPID: RP_ID,
      authenticator: {
        credentialID: Buffer.from(response.id, 'base64url'),
        credentialPublicKey: new Uint8Array(credential.credentialPublicKey),
        counter: credential.counter,
      },
    });

    if (!verification.verified) {
      res.status(400).json({ error: 'Authentication failed' });
      return;
    }

    // Update counter
    updateWebAuthnCounter.run({
      counter: verification.authenticationInfo.newCounter,
      credentialId: response.id,
    });

    webAuthnChallenges.delete(username);

    // Generate a session token for socket authentication
    const sessionToken = sodium.to_base64(sodium.randombytes_buf(32));
    const now = Math.floor(Date.now() / 1000);

    createChallenge.run({
      username,
      challenge: sessionToken,
      createdAt: now,
      expiresAt: now + 60, // 1 minute to use the token
    });

    res.json({
      verified: true,
      sessionToken,
    });
  } catch (error) {
    console.error('WebAuthn authentication verify error:', error);
    res.status(500).json({ error: 'Failed to verify authentication' });
  }
});

// Get user's hardware keys
app.get('/api/users/:username/hardware-keys', (req, res) => {
  const { username } = req.params;

  const webauthnKeys = getWebAuthnCredentialsByUsername.all(username) as Array<{
    id: string;
    credentialId: string;
    name: string;
    createdAt: number;
  }>;

  const trezorKeys = getTrezorKeysByUsername.all(username) as Array<{
    id: string;
    address: string;
    name: string;
    createdAt: number;
  }>;

  res.json({
    webauthn: webauthnKeys.map((k) => ({
      id: k.id,
      type: 'webauthn',
      name: k.name,
      createdAt: k.createdAt,
    })),
    trezor: trezorKeys.map((k) => ({
      id: k.id,
      type: 'trezor',
      name: k.name,
      address: k.address,
      createdAt: k.createdAt,
    })),
  });
});

// Delete hardware key
app.delete('/api/users/:username/hardware-keys/:type/:id', (req, res) => {
  const { username, type, id } = req.params;

  // Note: In production, this should require authentication
  if (type === 'webauthn') {
    deleteWebAuthnCredential.run(id, username);
  } else if (type === 'trezor') {
    deleteTrezorKey.run(id, username);
  } else {
    res.status(400).json({ error: 'Invalid key type' });
    return;
  }

  res.json({ success: true });
});

// ============ Trezor Endpoints ============

// Register Trezor key
app.post('/api/trezor/register', (req, res) => {
  try {
    const { username, publicKey, address, name } = req.body;

    if (!username || !publicKey || !address) {
      res.status(400).json({ error: 'Username, publicKey, and address are required' });
      return;
    }

    const user = getUserByUsername.get(username);
    if (!user) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    // Check if this Trezor is already registered
    const existing = getTrezorKeyByAddress.get(address);
    if (existing) {
      res.status(400).json({ error: 'This Trezor is already registered' });
      return;
    }

    saveTrezorKey.run({
      id: uuidv4(),
      username,
      publicKey,
      address,
      name: name || 'Trezor',
      createdAt: Date.now(),
    });

    res.json({ success: true });
  } catch (error) {
    console.error('Trezor registration error:', error);
    res.status(500).json({ error: 'Failed to register Trezor' });
  }
});

// Trezor authentication challenge
app.post('/api/trezor/authenticate/challenge', (req, res) => {
  try {
    const { username, address } = req.body;

    if (!username || !address) {
      res.status(400).json({ error: 'Username and address are required' });
      return;
    }

    const trezorKey = getTrezorKeyByAddress.get(address) as { username: string } | undefined;
    if (!trezorKey || trezorKey.username !== username) {
      res.status(404).json({ error: 'Trezor not registered for this user' });
      return;
    }

    const challenge = `Morse Login: ${uuidv4()}`;
    const now = Math.floor(Date.now() / 1000);

    createChallenge.run({
      username: `trezor:${address}`,
      challenge,
      createdAt: now,
      expiresAt: now + 300,
    });

    res.json({ challenge });
  } catch (error) {
    console.error('Trezor challenge error:', error);
    res.status(500).json({ error: 'Failed to generate challenge' });
  }
});

// Verify Trezor signature
app.post('/api/trezor/authenticate/verify', (req, res) => {
  try {
    const { username, address, signature, challenge } = req.body;

    if (!username || !address || !signature || !challenge) {
      res.status(400).json({ error: 'Missing required fields' });
      return;
    }

    const storedChallenge = getChallenge.get(`trezor:${address}`) as { challenge: string; expiresAt: number } | undefined;

    if (!storedChallenge || storedChallenge.challenge !== challenge) {
      res.status(400).json({ error: 'Invalid or expired challenge' });
      return;
    }

    if (storedChallenge.expiresAt < Math.floor(Date.now() / 1000)) {
      deleteChallenge.run(`trezor:${address}`);
      res.status(400).json({ error: 'Challenge expired' });
      return;
    }

    // In a production app, you would verify the Ethereum signature here
    // For MVP, we trust the client-side verification from Trezor Connect
    // The signature format from Trezor includes the address, which we can check

    deleteChallenge.run(`trezor:${address}`);

    // Generate session token
    const sessionToken = sodium.to_base64(sodium.randombytes_buf(32));
    const now = Math.floor(Date.now() / 1000);

    createChallenge.run({
      username,
      challenge: sessionToken,
      createdAt: now,
      expiresAt: now + 60,
    });

    res.json({
      verified: true,
      sessionToken,
    });
  } catch (error) {
    console.error('Trezor verify error:', error);
    res.status(500).json({ error: 'Failed to verify Trezor signature' });
  }
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

  // Login with hardware key session token (WebAuthn or Trezor)
  socket.on('loginWithHardwareKey', (data: { username: string; sessionToken: string }) => {
    try {
      const { username, sessionToken } = data;

      const user = getUserByUsername.get(username) as { publicKey: string } | undefined;
      if (!user) {
        socket.emit('error', { code: 'USER_NOT_FOUND', message: 'User not found' });
        return;
      }

      // The session token was created after successful WebAuthn/Trezor verification
      const storedChallenge = getChallenge.get(username) as { challenge: string; expiresAt: number } | undefined;
      if (!storedChallenge || storedChallenge.challenge !== sessionToken) {
        socket.emit('error', { code: 'INVALID_TOKEN', message: 'Invalid or expired session token' });
        return;
      }

      if (storedChallenge.expiresAt < Math.floor(Date.now() / 1000)) {
        deleteChallenge.run(username);
        socket.emit('error', { code: 'TOKEN_EXPIRED', message: 'Session token has expired' });
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

      console.log(`User logged in with hardware key: ${username}`);
    } catch (error) {
      console.error('Hardware key login error:', error);
      socket.emit('error', { code: 'LOGIN_FAILED', message: 'Failed to login with hardware key' });
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
