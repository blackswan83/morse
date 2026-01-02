import sodium from 'libsodium-wrappers';

// Wait for sodium to be ready
let isReady = false;
export const ready = sodium.ready.then(() => {
  isReady = true;
});

export function ensureReady() {
  if (!isReady) {
    throw new Error('Crypto library not initialized. Call `await ready` first.');
  }
}

// Key types
export interface IdentityKeyPair {
  publicKey: Uint8Array;
  privateKey: Uint8Array;
}

export interface KeyBundle {
  identityKeyPair: IdentityKeyPair;
  signedPreKeyPair: {
    publicKey: Uint8Array;
    privateKey: Uint8Array;
  };
  signedPreKeySignature: Uint8Array;
  oneTimePreKeyPairs: Array<{
    publicKey: Uint8Array;
    privateKey: Uint8Array;
  }>;
}

export interface SerializedKeyBundle {
  identityKey: string;
  signedPreKey: string;
  signedPreKeySignature: string;
  oneTimePreKeys: string[];
}

// Generate a new identity key pair (Ed25519 for signing)
export function generateIdentityKeyPair(): IdentityKeyPair {
  ensureReady();
  const keyPair = sodium.crypto_sign_keypair();
  return {
    publicKey: keyPair.publicKey,
    privateKey: keyPair.privateKey,
  };
}

// Generate a key exchange key pair (X25519)
export function generateKeyExchangeKeyPair() {
  ensureReady();
  const keyPair = sodium.crypto_kx_keypair();
  return {
    publicKey: keyPair.publicKey,
    privateKey: keyPair.privateKey,
  };
}

// Sign data with identity key
export function sign(data: Uint8Array, privateKey: Uint8Array): Uint8Array {
  ensureReady();
  return sodium.crypto_sign_detached(data, privateKey);
}

// Verify signature
export function verify(signature: Uint8Array, data: Uint8Array, publicKey: Uint8Array): boolean {
  ensureReady();
  try {
    return sodium.crypto_sign_verify_detached(signature, data, publicKey);
  } catch {
    return false;
  }
}

// Convert Ed25519 key to X25519 for key exchange
export function ed25519ToX25519Public(ed25519PublicKey: Uint8Array): Uint8Array {
  ensureReady();
  return sodium.crypto_sign_ed25519_pk_to_curve25519(ed25519PublicKey);
}

export function ed25519ToX25519Private(ed25519PrivateKey: Uint8Array): Uint8Array {
  ensureReady();
  return sodium.crypto_sign_ed25519_sk_to_curve25519(ed25519PrivateKey);
}

// Generate complete key bundle for registration
export function generateKeyBundle(oneTimeKeyCount = 10): KeyBundle {
  ensureReady();

  // Generate identity key pair (Ed25519)
  const identityKeyPair = generateIdentityKeyPair();

  // Generate signed pre-key (X25519)
  const signedPreKeyPair = sodium.crypto_box_keypair();

  // Sign the pre-key with identity key
  const signedPreKeySignature = sign(signedPreKeyPair.publicKey, identityKeyPair.privateKey);

  // Generate one-time pre-keys
  const oneTimePreKeyPairs: Array<{ publicKey: Uint8Array; privateKey: Uint8Array }> = [];
  for (let i = 0; i < oneTimeKeyCount; i++) {
    const keyPair = sodium.crypto_box_keypair();
    oneTimePreKeyPairs.push({
      publicKey: keyPair.publicKey,
      privateKey: keyPair.privateKey,
    });
  }

  return {
    identityKeyPair,
    signedPreKeyPair,
    signedPreKeySignature,
    oneTimePreKeyPairs,
  };
}

// Serialize key bundle for transmission to server
export function serializeKeyBundle(bundle: KeyBundle): SerializedKeyBundle {
  ensureReady();
  return {
    identityKey: sodium.to_base64(bundle.identityKeyPair.publicKey),
    signedPreKey: sodium.to_base64(bundle.signedPreKeyPair.publicKey),
    signedPreKeySignature: sodium.to_base64(bundle.signedPreKeySignature),
    oneTimePreKeys: bundle.oneTimePreKeyPairs.map(kp => sodium.to_base64(kp.publicKey)),
  };
}

// Derive shared secret using X3DH-like key agreement
export function deriveSharedSecret(
  myIdentityPrivate: Uint8Array,
  myEphemeralPrivate: Uint8Array,
  theirIdentityPublic: Uint8Array,
  theirSignedPreKeyPublic: Uint8Array,
  theirOneTimePreKeyPublic?: Uint8Array
): Uint8Array {
  ensureReady();

  // Convert identity keys to X25519
  const myIdentityX25519 = ed25519ToX25519Private(myIdentityPrivate);
  const theirIdentityX25519 = ed25519ToX25519Public(theirIdentityPublic);

  // DH1 = DH(IKa, SPKb)
  const dh1 = sodium.crypto_scalarmult(myIdentityX25519, theirSignedPreKeyPublic);

  // DH2 = DH(EKa, IKb)
  const dh2 = sodium.crypto_scalarmult(myEphemeralPrivate, theirIdentityX25519);

  // DH3 = DH(EKa, SPKb)
  const dh3 = sodium.crypto_scalarmult(myEphemeralPrivate, theirSignedPreKeyPublic);

  // Combine DH outputs
  let combined: Uint8Array;
  if (theirOneTimePreKeyPublic) {
    // DH4 = DH(EKa, OPKb)
    const dh4 = sodium.crypto_scalarmult(myEphemeralPrivate, theirOneTimePreKeyPublic);
    combined = new Uint8Array([...dh1, ...dh2, ...dh3, ...dh4]);
  } else {
    combined = new Uint8Array([...dh1, ...dh2, ...dh3]);
  }

  // Derive final key using HKDF (via generic hash)
  return sodium.crypto_generichash(32, combined);
}

// Derive shared secret for recipient (inverse of above)
export function deriveSharedSecretRecipient(
  myIdentityPrivate: Uint8Array,
  mySignedPreKeyPrivate: Uint8Array,
  myOneTimePreKeyPrivate: Uint8Array | undefined,
  theirIdentityPublic: Uint8Array,
  theirEphemeralPublic: Uint8Array
): Uint8Array {
  ensureReady();

  // Convert identity keys to X25519
  const myIdentityX25519 = ed25519ToX25519Private(myIdentityPrivate);
  const theirIdentityX25519 = ed25519ToX25519Public(theirIdentityPublic);

  // DH1 = DH(SPKb, IKa)
  const dh1 = sodium.crypto_scalarmult(mySignedPreKeyPrivate, theirIdentityX25519);

  // DH2 = DH(IKb, EKa)
  const dh2 = sodium.crypto_scalarmult(myIdentityX25519, theirEphemeralPublic);

  // DH3 = DH(SPKb, EKa)
  const dh3 = sodium.crypto_scalarmult(mySignedPreKeyPrivate, theirEphemeralPublic);

  // Combine DH outputs
  let combined: Uint8Array;
  if (myOneTimePreKeyPrivate) {
    // DH4 = DH(OPKb, EKa)
    const dh4 = sodium.crypto_scalarmult(myOneTimePreKeyPrivate, theirEphemeralPublic);
    combined = new Uint8Array([...dh1, ...dh2, ...dh3, ...dh4]);
  } else {
    combined = new Uint8Array([...dh1, ...dh2, ...dh3]);
  }

  // Derive final key using HKDF
  return sodium.crypto_generichash(32, combined);
}

// Encrypt a message with a shared secret
export function encrypt(
  plaintext: string,
  sharedSecret: Uint8Array
): { ciphertext: Uint8Array; nonce: Uint8Array } {
  ensureReady();

  const nonce = sodium.randombytes_buf(sodium.crypto_secretbox_NONCEBYTES);
  const plaintextBytes = sodium.from_string(plaintext);
  const ciphertext = sodium.crypto_secretbox_easy(plaintextBytes, nonce, sharedSecret);

  return { ciphertext, nonce };
}

// Decrypt a message with a shared secret
export function decrypt(
  ciphertext: Uint8Array,
  nonce: Uint8Array,
  sharedSecret: Uint8Array
): string {
  ensureReady();

  const plaintextBytes = sodium.crypto_secretbox_open_easy(ciphertext, nonce, sharedSecret);
  return sodium.to_string(plaintextBytes);
}

// Generate ephemeral key pair for key exchange
export function generateEphemeralKeyPair() {
  ensureReady();
  return sodium.crypto_box_keypair();
}

// Generate random nonce
export function generateNonce(): Uint8Array {
  ensureReady();
  return sodium.randombytes_buf(32);
}

// Base64 helpers
export function toBase64(data: Uint8Array): string {
  ensureReady();
  return sodium.to_base64(data);
}

export function fromBase64(data: string): Uint8Array {
  ensureReady();
  return sodium.from_base64(data);
}

// Generate recovery phrase (BIP39-style mnemonic)
const WORDLIST = [
  'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract',
  'absurd', 'abuse', 'access', 'accident', 'account', 'accuse', 'achieve', 'acid',
  'acoustic', 'acquire', 'across', 'act', 'action', 'actor', 'actress', 'actual',
  'adapt', 'add', 'addict', 'address', 'adjust', 'admit', 'adult', 'advance',
  'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again', 'age', 'agent',
  'agree', 'ahead', 'aim', 'air', 'airport', 'aisle', 'alarm', 'album',
  'alcohol', 'alert', 'alien', 'all', 'alley', 'allow', 'almost', 'alone',
  'alpha', 'already', 'also', 'alter', 'always', 'amateur', 'amazing', 'among',
  'amount', 'amused', 'analyst', 'anchor', 'ancient', 'anger', 'angle', 'angry',
  'animal', 'ankle', 'announce', 'annual', 'answer', 'antenna', 'antique', 'anxiety',
  'any', 'apart', 'apology', 'appear', 'apple', 'approve', 'april', 'arch',
  'arctic', 'area', 'arena', 'argue', 'arm', 'armed', 'armor', 'army',
  'around', 'arrange', 'arrest', 'arrive', 'arrow', 'art', 'artefact', 'artist',
  'artwork', 'ask', 'aspect', 'assault', 'asset', 'assist', 'assume', 'asthma',
  'athlete', 'atom', 'attack', 'attend', 'attitude', 'attract', 'auction', 'audit',
  'august', 'aunt', 'author', 'auto', 'autumn', 'average', 'avocado', 'avoid',
  'awake', 'aware', 'away', 'awesome', 'awful', 'awkward', 'axis', 'baby',
  'bachelor', 'bacon', 'badge', 'bag', 'balance', 'balcony', 'ball', 'bamboo',
  'banana', 'banner', 'bar', 'barely', 'bargain', 'barrel', 'base', 'basic',
  'basket', 'battle', 'beach', 'bean', 'beauty', 'because', 'become', 'beef',
  'before', 'begin', 'behave', 'behind', 'believe', 'below', 'belt', 'bench',
  'benefit', 'best', 'betray', 'better', 'between', 'beyond', 'bicycle', 'bid',
  'bike', 'bind', 'biology', 'bird', 'birth', 'bitter', 'black', 'blade',
  'blame', 'blanket', 'blast', 'bleak', 'bless', 'blind', 'blood', 'blossom',
  'blouse', 'blue', 'blur', 'blush', 'board', 'boat', 'body', 'boil',
  'bomb', 'bone', 'bonus', 'book', 'boost', 'border', 'boring', 'borrow',
  'boss', 'bottom', 'bounce', 'box', 'boy', 'bracket', 'brain', 'brand',
  'brave', 'bread', 'breeze', 'brick', 'bridge', 'brief', 'bright', 'bring',
  'brisk', 'broccoli', 'broken', 'bronze', 'broom', 'brother', 'brown', 'brush',
  'bubble', 'buddy', 'budget', 'buffalo', 'build', 'bulb', 'bulk', 'bullet',
  'bundle', 'bunker', 'burden', 'burger', 'burst', 'bus', 'business', 'busy',
  'butter', 'buyer', 'buzz', 'cabbage', 'cabin', 'cable', 'cactus', 'cage',
  'cake', 'call', 'calm', 'camera', 'camp', 'can', 'canal', 'cancel',
  'candy', 'cannon', 'canoe', 'canvas', 'canyon', 'capable', 'capital', 'captain',
];

export function generateRecoveryPhrase(): string {
  ensureReady();
  const entropy = sodium.randombytes_buf(32);
  const words: string[] = [];

  for (let i = 0; i < 24; i++) {
    const index = (entropy[i] + (entropy[(i + 1) % 32] << 8)) % WORDLIST.length;
    words.push(WORDLIST[index]);
  }

  return words.join(' ');
}

export function deriveKeyFromPhrase(phrase: string): Uint8Array {
  ensureReady();
  const phraseBytes = sodium.from_string(phrase);
  return sodium.crypto_generichash(32, phraseBytes);
}
