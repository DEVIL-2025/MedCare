import { useState, useRef, useEffect } from 'react';
import { Bot, Sparkles, X, Send, RotateCcw, ChevronRight } from 'lucide-react';
import { api } from '../../api/client';

const INITIAL_MESSAGE = {
  id: 'init-1',
  sender: 'assistant',
  text: 'Hello! I am your MedCare SCM Control Tower AI Assistant, connected live to PostgreSQL.\n\nAsk me about real-time inventory levels, ML demand forecasts, FEFO near-expiry batches, replenishment recommendations, active alerts, or distribution center capacities.',
  category: 'System',
  timestamp: new Date(),
  suggested_actions: [
    'What is the stock of Paracetamol in MUM-01?',
    'What is the demand forecast for Paracetamol in BLR-01?',
    'Which batches are expiring soon?',
    'What purchase orders are recommended?',
    'Are there any critical stockout alerts?'
  ]
};

function formatMessageText(text) {
  if (!text) return null;
  const lines = text.split('\n');

  return lines.map((line, lineIdx) => {
    if (!line.trim()) {
      return <div key={lineIdx} className="h-1.5" />;
    }

    const isBullet = line.trim().startsWith('•') || line.trim().startsWith('- ') || line.trim().startsWith('* ');
    const cleanedLine = isBullet ? line.trim().replace(/^([•\-\*]\s*)/, '') : line;

    const parts = cleanedLine.split(/(\*\*.*?\*\*)/g);
    const renderedParts = parts.map((part, partIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={partIdx} className="font-semibold text-ink-900">{part.slice(2, -2)}</strong>;
      }
      return part;
    });

    if (isBullet) {
      return (
        <div key={lineIdx} className="flex items-start gap-1.5 my-0.5 pl-1">
          <span className="text-forest-700 font-bold leading-tight select-none">•</span>
          <span className="flex-1 leading-relaxed text-ink-800">{renderedParts}</span>
        </div>
      );
    }

    if (line.startsWith('### ') || line.startsWith('## ') || line.startsWith('# ')) {
      const headerText = line.replace(/^#+\s*/, '');
      return (
        <div key={lineIdx} className="font-bold text-forest-900 mt-2 mb-1 text-[13px]">
          {headerText}
        </div>
      );
    }

    return (
      <p key={lineIdx} className="leading-relaxed text-ink-800 my-0.5">
        {renderedParts}
      </p>
    );
  });
}

export default function ChatWidget({ isOpen, onClose }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen, messages, loading]);

  async function handleSend(queryToSend) {
    const q = (queryToSend || input).trim();
    if (!q || loading) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: q,
      timestamp: new Date()
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryToSend) setInput('');
    setError(null);
    setLoading(true);

    try {
      const res = await api.chatWithAssistant({ query: q });
      const botMsg = {
        id: `bot-${Date.now()}`,
        sender: 'assistant',
        text: res.answer || 'No response returned from assistant.',
        category: res.category || 'General',
        confidence: res.confidence,
        suggested_actions: res.suggested_actions || [],
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error('Chat error:', err);
      const errorMsg = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        text: `⚠️ **Error querying Control Tower**: ${err.message || 'Unable to connect to assistant service. Please verify server status.'}`,
        category: 'Error',
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, errorMsg]);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleClearChat() {
    setMessages([INITIAL_MESSAGE]);
    setError(null);
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-ink-900/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Slide-over Drawer */}
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl border-l border-ink-100 flex flex-col animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="bg-forest-800 text-white px-5 py-3.5 flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-forest-700 flex items-center justify-center border border-forest-600/50 shadow-xs">
                <Bot size={18} className="text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-[14px] font-bold tracking-tight">MedCare SCM Assistant</h3>
                  <span className="text-[9.5px] font-mono px-1.5 py-0.2 bg-forest-900/60 rounded text-emerald-300 border border-emerald-500/30">
                    Live Grounded
                  </span>
                </div>
                <p className="text-[11px] text-cream-200/80">PostgreSQL + Gemini 2.0 Flash</p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={handleClearChat}
                className="p-1.5 text-cream-200/70 hover:text-white hover:bg-forest-700/60 rounded transition-colors"
                title="Reset conversation"
              >
                <RotateCcw size={15} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 text-cream-200/70 hover:text-white hover:bg-forest-700/60 rounded transition-colors"
                title="Close drawer"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-cream-100/40 text-[12.5px]">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
              >
                {/* Category tag for assistant */}
                {msg.sender === 'assistant' && msg.category && msg.category !== 'System' && (
                  <span className="text-[10px] font-semibold text-ink-500 uppercase tracking-wider px-1 mb-1 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-forest-600 inline-block" />
                    {msg.category}
                  </span>
                )}

                {/* Message Bubble */}
                <div
                  className={`p-3.5 rounded-lg shadow-card leading-relaxed ${
                    msg.sender === 'user'
                      ? 'bg-forest-800 text-white rounded-tr-none max-w-[85%]'
                      : 'bg-white border border-ink-100 rounded-tl-none max-w-[92%] text-ink-900'
                  }`}
                >
                  {msg.sender === 'user' ? (
                    <p className="text-[12.5px]">{msg.text}</p>
                  ) : (
                    <div>{formatMessageText(msg.text)}</div>
                  )}
                </div>

                {/* Suggested Action Chips */}
                {msg.suggested_actions && msg.suggested_actions.length > 0 && (
                  <div className="mt-2 space-y-1 w-full max-w-[92%]">
                    <p className="text-[10.5px] font-semibold text-ink-500 mb-1">Suggested inquiries:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.suggested_actions.map((act, i) => (
                        <button
                          key={i}
                          onClick={() => handleSend(act)}
                          disabled={loading}
                          className="text-[11px] px-2.5 py-1 bg-white hover:bg-cream-200 border border-ink-200 text-forest-900 rounded-md font-medium text-left transition-colors shadow-2xs flex items-center gap-1 cursor-pointer disabled:opacity-50"
                        >
                          <ChevronRight size={11} className="text-forest-600" />
                          <span>{act}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Loading Indicator */}
            {loading && (
              <div className="flex items-center gap-2 text-ink-500 bg-white border border-ink-100 rounded-lg rounded-tl-none p-3 max-w-[80%] shadow-card">
                <Sparkles size={14} className="text-forest-600 animate-spin" />
                <span className="text-[11.5px] italic">Consulting PostgreSQL & Gemini...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="p-3 bg-white border-t border-ink-100 flex items-center gap-2"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about inventory, demand forecasts, alerts..."
              className="flex-1 text-[12.5px] px-3 py-2 border border-ink-200 rounded-md focus:outline-none focus:border-forest-600 bg-cream-100/40 text-ink-900 placeholder:text-ink-400"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="p-2 bg-forest-800 hover:bg-forest-700 text-white rounded-md transition-colors disabled:opacity-40 cursor-pointer shadow-xs"
              title="Send message"
            >
              <Send size={15} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
