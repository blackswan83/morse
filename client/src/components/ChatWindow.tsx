import { useState, useRef, useEffect } from 'react';
import { useAppStore } from '../store';

export function ChatWindow() {
  const [messageInput, setMessageInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { selectedContact, contacts, messages, sendMessage, selectContact } = useAppStore();

  const contact = selectedContact ? contacts.get(selectedContact) : null;
  const chatMessages = messages.filter(m => m.contactUsername === selectedContact);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageInput.trim() || !selectedContact) return;

    const content = messageInput.trim();
    setMessageInput('');

    try {
      await sendMessage(selectedContact, content);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  if (!contact) return null;

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b border-morse-800 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => selectContact(null)}
            className="lg:hidden p-2 -ml-2 text-morse-400 hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="relative">
            <div className="w-10 h-10 bg-morse-700 rounded-full flex items-center justify-center">
              <span className="text-white font-medium">
                {contact.username[0].toUpperCase()}
              </span>
            </div>
            {contact.online && (
              <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-500 border-2 border-morse-950 rounded-full" />
            )}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-medium text-white">{contact.username}</span>
              {contact.verified && (
                <span className="px-2 py-0.5 bg-morse-600/50 text-morse-300 text-xs rounded-full flex items-center space-x-1">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  <span>Verified</span>
                </span>
              )}
            </div>
            <span className="text-xs text-morse-400">
              {contact.online ? 'Online' : 'Offline'}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 px-3 py-1.5 bg-morse-800/50 rounded-lg text-xs text-morse-400">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <span>End-to-end encrypted</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {chatMessages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-morse-800 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-morse-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className="text-morse-400">No messages yet</p>
              <p className="text-morse-500 text-sm mt-1">Send a message to start the conversation</p>
            </div>
          </div>
        ) : (
          <>
            {chatMessages.map((message, index) => {
              const showTimestamp =
                index === 0 ||
                message.timestamp - chatMessages[index - 1].timestamp > 300000;

              return (
                <div key={message.id}>
                  {showTimestamp && (
                    <div className="text-center my-4">
                      <span className="text-xs text-morse-500 bg-morse-900 px-3 py-1 rounded-full">
                        {formatMessageTime(message.timestamp)}
                      </span>
                    </div>
                  )}
                  <div className={`flex ${message.sent ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[70%] px-4 py-2 rounded-2xl ${
                        message.sent
                          ? 'bg-morse-600 text-white rounded-br-md'
                          : 'bg-morse-800 text-white rounded-bl-md'
                      }`}
                    >
                      <p className="break-words">{message.content}</p>
                      <div className={`flex items-center justify-end space-x-1 mt-1 ${
                        message.sent ? 'text-morse-300' : 'text-morse-500'
                      }`}>
                        <span className="text-[10px]">
                          {new Date(message.timestamp).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                        {message.sent && (
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-morse-800">
        <form onSubmit={handleSend} className="flex space-x-3">
          <input
            type="text"
            value={messageInput}
            onChange={(e) => setMessageInput(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 input-field"
          />
          <button
            type="submit"
            disabled={!messageInput.trim()}
            className="btn-primary px-6"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}

function formatMessageTime(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  if (diff < 86400000) {
    return 'Today';
  } else if (diff < 172800000) {
    return 'Yesterday';
  } else {
    return date.toLocaleDateString([], {
      weekday: 'long',
      month: 'short',
      day: 'numeric',
    });
  }
}
