import { useAppStore } from '../store';

interface SidebarProps {
  onAddContact: () => void;
  onUltraVerify: () => void;
  onSettings: () => void;
  onPhone: () => void;
  onSms: () => void;
}

export function Sidebar({ onAddContact, onUltraVerify, onSettings, onPhone, onSms }: SidebarProps) {
  const { username, contacts, selectedContact, selectContact, connected, messages } = useAppStore();

  const contactsList = Array.from(contacts.values()).sort((a, b) => {
    // Sort by most recent message
    const aLastMsg = messages.filter(m => m.contactUsername === a.username).pop();
    const bLastMsg = messages.filter(m => m.contactUsername === b.username).pop();
    if (aLastMsg && bLastMsg) return bLastMsg.timestamp - aLastMsg.timestamp;
    if (aLastMsg) return -1;
    if (bLastMsg) return 1;
    return b.addedAt - a.addedAt;
  });

  const getLastMessage = (contactUsername: string) => {
    const contactMessages = messages.filter(m => m.contactUsername === contactUsername);
    return contactMessages[contactMessages.length - 1];
  };

  return (
    <div className="w-80 bg-morse-900/50 border-r border-morse-800 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-morse-800">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-br from-morse-400 to-morse-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-semibold text-lg">
                {username?.[0].toUpperCase()}
              </span>
            </div>
            <div>
              <div className="font-medium text-white">{username}</div>
              <div className="flex items-center text-xs text-morse-400">
                <span className={`w-2 h-2 rounded-full mr-1.5 ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
                {connected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
          </div>
          <button
            onClick={onSettings}
            className="p-2 text-morse-400 hover:text-white hover:bg-morse-800 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>

        <div className="flex space-x-2">
          <button
            onClick={onAddContact}
            className="flex-1 btn-secondary text-sm flex items-center justify-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
            <span>Add</span>
          </button>
          <button
            onClick={onUltraVerify}
            className="flex-1 btn-primary text-sm flex items-center justify-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
            </svg>
            <span>Ultra</span>
          </button>
        </div>

        {/* Phone and SMS buttons */}
        <div className="flex space-x-2 mt-2">
          <button
            onClick={onPhone}
            className="flex-1 btn-secondary text-sm flex items-center justify-center space-x-2"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 00-1.01.24l-1.57 1.97c-2.83-1.35-5.48-3.9-6.89-6.83l1.95-1.66c.27-.28.35-.67.24-1.02-.37-1.11-.56-2.3-.56-3.53 0-.54-.45-.99-.99-.99H4.19C3.65 3 3 3.24 3 3.99 3 13.28 10.73 21 20.01 21c.71 0 .99-.63.99-1.18v-3.45c0-.54-.45-.99-.99-.99z" />
            </svg>
            <span>Phone</span>
          </button>
          <button
            onClick={onSms}
            className="flex-1 btn-secondary text-sm flex items-center justify-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
            <span>SMS</span>
          </button>
        </div>
      </div>

      {/* Contacts List */}
      <div className="flex-1 overflow-y-auto">
        {contactsList.length === 0 ? (
          <div className="p-6 text-center">
            <div className="w-16 h-16 mx-auto mb-4 bg-morse-800 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 text-morse-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <p className="text-morse-400 text-sm">No contacts yet</p>
            <p className="text-morse-500 text-xs mt-1">Add a contact to start messaging</p>
          </div>
        ) : (
          <div className="py-2">
            {contactsList.map((contact) => {
              const lastMessage = getLastMessage(contact.username);
              const isSelected = selectedContact === contact.username;

              return (
                <button
                  key={contact.username}
                  onClick={() => selectContact(contact.username)}
                  className={`w-full px-4 py-3 flex items-center space-x-3 hover:bg-morse-800/50 transition-colors ${
                    isSelected ? 'bg-morse-800' : ''
                  }`}
                >
                  <div className="relative">
                    <div className="w-12 h-12 bg-morse-700 rounded-full flex items-center justify-center">
                      <span className="text-white font-medium text-lg">
                        {contact.username[0].toUpperCase()}
                      </span>
                    </div>
                    {contact.online && (
                      <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-morse-900 rounded-full" />
                    )}
                    {contact.verified && (
                      <span className="absolute -top-1 -right-1 w-5 h-5 bg-morse-600 rounded-full flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-white truncate">{contact.username}</span>
                      {lastMessage && (
                        <span className="text-xs text-morse-500">
                          {formatTime(lastMessage.timestamp)}
                        </span>
                      )}
                    </div>
                    {lastMessage && (
                      <p className="text-sm text-morse-400 truncate">
                        {lastMessage.sent ? 'You: ' : ''}{lastMessage.content}
                      </p>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  if (diff < 60000) return 'now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
  if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
