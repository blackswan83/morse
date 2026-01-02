import { useState } from 'react';
import { useAppStore } from '../store';
import { Sidebar } from './Sidebar';
import { ChatWindow } from './ChatWindow';
import { AddContactModal } from './AddContactModal';
import { UltraVerifyModal } from './UltraVerifyModal';
import { SettingsModal } from './SettingsModal';

export function Chat() {
  const [showAddContact, setShowAddContact] = useState(false);
  const [showUltraVerify, setShowUltraVerify] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const { selectedContact } = useAppStore();

  return (
    <div className="h-full flex bg-morse-950">
      <Sidebar
        onAddContact={() => setShowAddContact(true)}
        onUltraVerify={() => setShowUltraVerify(true)}
        onSettings={() => setShowSettings(true)}
      />

      <div className="flex-1 flex flex-col">
        {selectedContact ? (
          <ChatWindow />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="w-24 h-24 mx-auto mb-6 bg-morse-900 rounded-full flex items-center justify-center">
                <svg className="w-12 h-12 text-morse-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">Welcome to Morse</h2>
              <p className="text-morse-400 max-w-sm">
                Select a contact to start a secure conversation, or add a new contact.
              </p>
            </div>
          </div>
        )}
      </div>

      {showAddContact && (
        <AddContactModal onClose={() => setShowAddContact(false)} />
      )}

      {showUltraVerify && (
        <UltraVerifyModal onClose={() => setShowUltraVerify(false)} />
      )}

      {showSettings && (
        <SettingsModal onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
}
