# Morse - Secure Messaging

End-to-end encrypted messaging with username-only registration and Ultra Protocol proximity verification.

## Features

- **Username-only registration** - No phone or email required
- **End-to-end encryption** - libsodium (X25519 + Ed25519)
- **X3DH-like key exchange** - Forward secrecy with pre-keys
- **Ultra Protocol** - QR-based proximity verification
- **Recovery phrase** - 24-word BIP39-style backup

## Architecture

```
morse/
├── client/          # React + Vite frontend
├── server/          # Node.js + Express + Socket.io backend
└── shared/          # Shared TypeScript types
```

## Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand
- **Backend**: Node.js, Express, Socket.io, better-sqlite3
- **Crypto**: libsodium-wrappers
- **QR**: qrcode, html5-qrcode

## Quick Start

```bash
# Install dependencies
npm install

# Start development servers
npm run dev
```

The client runs on `http://localhost:5173` and server on `http://localhost:3001`.

## Cryptographic Design

### Key Generation
- Identity key: Ed25519 (signing)
- Signed pre-key: X25519 (key exchange)
- One-time pre-keys: X25519 (forward secrecy)

### Key Exchange (X3DH-like)
1. Alice fetches Bob's key bundle
2. Generates ephemeral X25519 keypair
3. Computes shared secret from multiple DH operations
4. Derives symmetric key via HKDF

### Message Encryption
- AES-256-GCM via libsodium's secretbox
- Unique nonce per message

### Ultra Protocol
QR codes contain signed identity + ephemeral keys for in-person verification, preventing MITM attacks on contact addition.

## Security Notes

This is an MVP for prototyping. For production:
- Add Double Ratchet for message-level forward secrecy
- Implement sealed sender for metadata protection
- Add proper key rotation
- Security audit required

## License

MIT
