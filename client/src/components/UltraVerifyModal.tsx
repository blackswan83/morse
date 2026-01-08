import { useState, useEffect, useRef } from 'react';
import QRCode from 'qrcode';
import { Html5Qrcode } from 'html5-qrcode';
import { useAppStore } from '../store';
import { logger } from '../lib/logger';

interface UltraVerifyModalProps {
  onClose: () => void;
}

type Mode = 'choose' | 'show' | 'scan' | 'success' | 'error';

export function UltraVerifyModal({ onClose }: UltraVerifyModalProps) {
  const [mode, setMode] = useState<Mode>('choose');
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [verifiedUsername, setVerifiedUsername] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const scannerContainerRef = useRef<HTMLDivElement>(null);
  const { generateUltraPayload, verifyUltraPayload } = useAppStore();

  useEffect(() => {
    if (mode === 'show') {
      const payload = generateUltraPayload();
      if (payload) {
        QRCode.toDataURL(payload, {
          width: 280,
          margin: 2,
          color: {
            dark: '#0ea5e9',
            light: '#082f49',
          },
        }).then(setQrDataUrl);
      }
    }
  }, [mode, generateUltraPayload]);

  useEffect(() => {
    if (mode === 'scan' && scannerContainerRef.current) {
      const scannerId = 'ultra-qr-scanner';

      // Create scanner container
      scannerContainerRef.current.innerHTML = `<div id="${scannerId}"></div>`;

      const scanner = new Html5Qrcode(scannerId);
      scannerRef.current = scanner;

      scanner.start(
        { facingMode: 'environment' },
        {
          fps: 10,
          qrbox: { width: 250, height: 250 },
        },
        async (decodedText) => {
          // Stop scanner
          await scanner.stop();
          scannerRef.current = null;

          // Verify the payload
          const result = await verifyUltraPayload(decodedText);

          if (result.success && result.username) {
            setVerifiedUsername(result.username);
            setMode('success');
          } else {
            setErrorMessage(result.error || 'Verification failed');
            setMode('error');
          }
        },
        () => {
          // Ignore errors during scanning
        }
      ).catch((err) => {
        logger.error('Failed to start scanner', err);
        setErrorMessage('Failed to access camera. Please ensure camera permissions are granted.');
        setMode('error');
      });

      return () => {
        if (scannerRef.current) {
          scannerRef.current.stop().catch(() => {});
        }
      };
    }
  }, [mode, verifyUltraPayload]);

  const handleClose = async () => {
    if (scannerRef.current) {
      await scannerRef.current.stop().catch(() => {});
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
      <div className="card max-w-md w-full">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-morse-600/20 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-morse-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">Ultra Protocol</h2>
              <p className="text-sm text-morse-400">In-person verification</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-morse-400 hover:text-white hover:bg-morse-800 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {mode === 'choose' && (
          <>
            <p className="text-morse-400 mb-6">
              Ultra Protocol provides cryptographic verification that you're talking to the right person.
              Meet in person and scan each other's QR codes.
            </p>

            <div className="space-y-3">
              <button
                onClick={() => setMode('show')}
                className="w-full p-4 bg-morse-800 hover:bg-morse-700 rounded-xl flex items-center space-x-4 transition-colors"
              >
                <div className="w-12 h-12 bg-morse-600/30 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-morse-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                  </svg>
                </div>
                <div className="text-left">
                  <div className="font-medium text-white">Show My QR Code</div>
                  <div className="text-sm text-morse-400">Let someone scan your code</div>
                </div>
              </button>

              <button
                onClick={() => setMode('scan')}
                className="w-full p-4 bg-morse-800 hover:bg-morse-700 rounded-xl flex items-center space-x-4 transition-colors"
              >
                <div className="w-12 h-12 bg-morse-600/30 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-morse-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <div className="text-left">
                  <div className="font-medium text-white">Scan QR Code</div>
                  <div className="text-sm text-morse-400">Verify someone's identity</div>
                </div>
              </button>
            </div>

            <div className="mt-6 p-4 bg-morse-950 rounded-lg">
              <div className="flex items-start space-x-3">
                <svg className="w-5 h-5 text-morse-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                <div className="text-sm text-morse-400">
                  <p className="font-medium text-morse-300 mb-1">Why use Ultra Protocol?</p>
                  <p>
                    Regular contact adding trusts the server. Ultra Protocol verifies identity
                    through an unhackable visual channel - your eyes.
                  </p>
                </div>
              </div>
            </div>
          </>
        )}

        {mode === 'show' && (
          <>
            <div className="flex justify-center mb-6">
              {qrDataUrl ? (
                <div className="p-4 bg-morse-950 rounded-xl">
                  <img src={qrDataUrl} alt="Your Ultra QR Code" className="w-[280px] h-[280px]" />
                </div>
              ) : (
                <div className="w-[280px] h-[280px] bg-morse-800 rounded-xl flex items-center justify-center">
                  <svg className="animate-spin w-8 h-8 text-morse-500" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                </div>
              )}
            </div>

            <p className="text-center text-morse-400 mb-6">
              Have your contact scan this QR code to verify your identity
            </p>

            <button onClick={() => setMode('choose')} className="btn-secondary w-full">
              Back
            </button>
          </>
        )}

        {mode === 'scan' && (
          <>
            <div
              ref={scannerContainerRef}
              className="mb-6 rounded-xl overflow-hidden bg-morse-950"
              style={{ minHeight: '280px' }}
            />

            <p className="text-center text-morse-400 mb-6">
              Point your camera at someone's Ultra QR code
            </p>

            <button onClick={() => setMode('choose')} className="btn-secondary w-full">
              Cancel
            </button>
          </>
        )}

        {mode === 'success' && (
          <div className="text-center py-8">
            <div className="w-20 h-20 mx-auto mb-4 bg-green-500/20 rounded-full flex items-center justify-center">
              <svg className="w-10 h-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Verified!</h3>
            <p className="text-morse-400 mb-6">
              <span className="font-medium text-white">{verifiedUsername}</span> has been
              cryptographically verified
            </p>
            <button onClick={handleClose} className="btn-primary w-full">
              Done
            </button>
          </div>
        )}

        {mode === 'error' && (
          <div className="text-center py-8">
            <div className="w-20 h-20 mx-auto mb-4 bg-red-500/20 rounded-full flex items-center justify-center">
              <svg className="w-10 h-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Verification Failed</h3>
            <p className="text-morse-400 mb-6">{errorMessage}</p>
            <div className="flex space-x-3">
              <button onClick={() => setMode('choose')} className="flex-1 btn-secondary">
                Try Again
              </button>
              <button onClick={handleClose} className="flex-1 btn-primary">
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
