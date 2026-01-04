# Morse

**Secure, Private Communication Platform**

Morse is an end-to-end encrypted messaging platform designed with privacy and security at its core. Built for users who demand complete control over their communications, Morse combines military-grade encryption with a seamless user experience.

---

## Features

### 🔐 Zero-Knowledge Authentication

- **Username-only registration** — No phone number, email, or personal information required
- **24-word recovery phrase** — Cryptographically generated backup that only you control
- **No password storage** — Your identity is proven through cryptographic signatures, not stored secrets

### 🔒 End-to-End Encryption

- **X3DH Key Exchange** — Extended Triple Diffie-Hellman protocol for establishing secure sessions
- **libsodium cryptography** — Industry-standard encryption using:
  - X25519 for key exchange
  - Ed25519 for digital signatures
  - XSalsa20-Poly1305 for message encryption
- **Perfect forward secrecy** — Compromising one session doesn't affect past or future messages
- **One-time prekeys** — Each new conversation uses fresh cryptographic material

### 📱 Ultra Protocol — Proximity Verification

Verify contacts in person using QR codes to prevent man-in-the-middle attacks:

1. Generate a verification QR code containing your signed identity
2. Scan your contact's QR code when you meet in person
3. Both parties are now cryptographically verified
4. Verified contacts display a trusted badge

This ensures you're really talking to who you think you are — not an impersonator.

### 🔑 Hardware Security Key Support

Protect your account with physical security devices:

- **YubiKey / FIDO2** — WebAuthn-based authentication using security keys
- **Trezor** — Hardware wallet integration for cryptographic authentication
- **Multi-device support** — Register multiple hardware keys for backup

### 📞 Phone Calling (VoIP)

Make real phone calls to any number worldwide:

- **Browser-based calling** — No app download required
- **WebRTC audio** — High-quality, low-latency voice
- **Dial pad interface** — Familiar phone experience
- **Call history** — Track your outbound calls
- **DTMF support** — Navigate phone menus with touch tones

### 💬 SMS Messaging

Send text messages to real phone numbers:

- **Global SMS** — Reach any mobile number
- **Message history** — View sent messages and delivery status
- **Character counting** — See SMS segment breakdown
- **Credit-based billing** — Pay only for what you use

### 💳 Credit System

Transparent, prepaid billing for telephony:

- **Pay-as-you-go** — No subscriptions or hidden fees
- **Real-time balance** — Always know your remaining credits
- **Usage tracking** — Detailed logs of calls and messages

---

## Security Architecture

### Client-Side

| Component | Technology |
|-----------|------------|
| Encryption | libsodium (WebAssembly) |
| Key Storage | IndexedDB (encrypted) |
| Transport | WebSocket (TLS) |
| UI Framework | React + TypeScript |

### Server-Side

| Component | Technology |
|-----------|------------|
| Runtime | Node.js |
| Real-time | Socket.io |
| Database | SQLite |
| Auth | Cryptographic signatures |

### What the Server Knows

| Data | Stored? |
|------|---------|
| Username | ✅ Yes |
| Public keys | ✅ Yes |
| Message content | ❌ No (encrypted) |
| Contact list | ❌ No (client-side) |
| Private keys | ❌ No (never leaves device) |

---

## How It Works

### Registration Flow

```
1. User chooses username
2. Client generates Ed25519 identity keypair
3. Client generates X25519 signed prekey + one-time prekeys
4. Public keys uploaded to server
5. 24-word recovery phrase displayed (BIP39)
6. Keys stored locally in IndexedDB
```

### Message Flow

```
1. Sender retrieves recipient's key bundle
2. X3DH key exchange derives shared secret
3. Message encrypted with XSalsa20-Poly1305
4. Ciphertext sent via WebSocket
5. Recipient decrypts with shared secret
6. Plaintext never touches the server
```

### Ultra Verification Flow

```
1. User A generates QR with signed identity payload
2. User B scans QR code in person
3. Client verifies signature against stored public key
4. If valid, contact marked as "verified"
5. Mismatch triggers security warning
```

---

## Tech Stack

```
morse/
├── client/          # React + Vite frontend
├── server/          # Node.js + Express + Socket.io backend
└── shared/          # Shared TypeScript types
```

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand
- **Backend**: Node.js, Express, Socket.io, better-sqlite3
- **Crypto**: libsodium-wrappers
- **Hardware Keys**: @simplewebauthn, @trezor/connect-web
- **Telephony**: Twilio Voice SDK, Twilio API
- **QR Codes**: qrcode, html5-qrcode

---

## Getting Started

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/morse.git
cd morse

# Install dependencies
npm install

# Start development servers
npm run dev --workspace=server &
npm run dev --workspace=client
```

The client runs on `http://localhost:5173` and server on `http://localhost:3001`.

### Environment Variables

**Server** (`server/.env`):
```bash
PORT=3001
NODE_ENV=development

# For production
CORS_ORIGINS=https://your-client.app
ORIGIN=https://your-client.app
RP_ID=your-client.app

# Optional: Twilio for phone/SMS
TWILIO_ACCOUNT_SID=ACxxxxxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890
```

**Client** (`client/.env`):
```bash
VITE_API_URL=http://localhost:3001
VITE_WS_URL=http://localhost:3001
```

---

## Privacy Principles

1. **Minimal data collection** — We only store what's cryptographically necessary
2. **No metadata logging** — We don't track who talks to whom
3. **Client-side encryption** — Messages are encrypted before leaving your device
4. **Open protocols** — Standard cryptographic primitives, no proprietary algorithms
5. **No phone/email required** — True pseudonymous communication

---

## Security Notes

This is an MVP for prototyping. For production deployment:

- [ ] Add Double Ratchet for message-level forward secrecy
- [ ] Implement sealed sender for metadata protection
- [ ] Add proper key rotation mechanisms
- [ ] Conduct security audit
- [ ] Add rate limiting and abuse prevention

---

## Roadmap

- [ ] Group encrypted messaging
- [ ] Disappearing messages
- [ ] Encrypted file/image sharing
- [ ] Desktop apps (Electron)
- [ ] Mobile apps (React Native)
- [ ] Decentralized architecture
- [ ] Onion routing integration

---

## License

MIT

---

<p align="center">
  <strong>Morse</strong> — Communication without compromise.
</p>
