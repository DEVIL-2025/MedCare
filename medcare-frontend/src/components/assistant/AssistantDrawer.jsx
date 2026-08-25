import { useState, useRef, useEffect } from 'react';
import { Sparkles, Send, X, Bot, User, CornerDownLeft, RefreshCw, Layers, ArrowRight } from 'lucide-react';
import { api } from '../../api/client';
import { useControlTower } from '../../context/ControlTowerContext';

const DEFAULT_SUGGESTIONS = [
  'What is the stock of Paracetamol across our DCs?',
  'Which batches are expiring within the next 60 days?',
  'Show active replenishment recommendations',
  'Are there any critical stockout alerts?',
  'Show recent internal consumption records',
  'What is our regional warehouse status?'
];

export default function AssistantDrawer({ open, onClose }) {
  const { selectedWarehouse } = useControlTower();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      id: 'init-1',
      sender: 'assistant',
      text: '👋 Hello! I am your **MedCare AI Supply Chain Assistant**.\n\nI am connected live to your PostgreSQL database. Ask me any question about inventory balances, FEFO batch expiry, replenishment recommendations, alerts, transactions, or warehouse capacities.',
      category: 'Welcome',
      suggestions: DEFAULT_SUGGESTIONS.slice(0, 3)
    }
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (open) {
      scrollToBottom();
    }
  }, [open, messages]);

  async function handleSend(queryText = null) {
    const textToSend = (queryText || input).trim();
    if (!textToSend || loading) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.askAssistant({
        query: textToSend,
        warehouse: selectedWarehouse !== 'All' ? selectedWarehouse : undefined
      });

      if (res && res.answer) {
        const assistantMsg = {
          id: `bot-${Date.now()}`,
          sender: 'assistant',
          text: res.answer,
          category: res.category,
          confidence: res.confidence,
          suggestions: res.suggested_actions || []
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } else {
        throw new Error('No answer received from assistant');
      }
    } catch (err) {
      console.error('Assistant error:', err);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: `⚠️ **Unable to fetch database response**: ${err.message || 'Connection error'}. Please verify backend status.`,
          isError: true
        }
      ]);
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="absolute inset-0 bg-ink-900/40 backdrop-blur-xs transition-opacity"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col border-l border-ink-100">
          {/* Header */}
          <div className="p-4 bg-forest-900 text-white flex items-center justify-between shadow-xs">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-forest-600/80 flex items-center justify-center border border-white/10">
                <Sparkles size={16} className="text-cream-100" />
              </div>
              <div>
                <h3 className="text-[14px] font-bold leading-tight">AI Supply Chain Assistant</h3>
                <span className="text-[11px] text-cream-100/60 font-mono">Live PostgreSQL Grounded</span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-md text-cream-100/70 hover:text-white hover:bg-forest-800 transition-colors cursor-pointer"
            >
              <X size={18} />
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-cream-100/40 text-[12.5px]">
            {messages.map((m) => {
              const isUser = m.sender === 'user';
              return (
                <div
                  key={m.id}
                  className={`flex gap-2.5 ${isUser ? 'justify-end' : 'justify-start'}`}
                >
                  {!isUser && (
                    <div className="w-6 h-6 rounded-full bg-forest-700 text-white flex items-center justify-center shrink-0 mt-0.5">
                      <Bot size={13} />
                    </div>
                  )}

                  <div className={`max-w-[85%] space-y-2`}>
                    <div
                      className={`p-3 rounded-xl shadow-xs whitespace-pre-wrap leading-relaxed ${
                        isUser
                          ? 'bg-forest-700 text-white rounded-br-none'
                          : m.isError
                          ? 'bg-brick-50 border border-brick-200 text-brick-900 rounded-bl-none'
                          : 'bg-white border border-ink-100 text-ink-800 rounded-bl-none'
                      }`}
                    >
                      {m.text}
                    </div>

                    {/* Suggestions */}
                    {!isUser && m.suggestions && m.suggestions.length > 0 && (
                      <div className="space-y-1 pt-1">
                        <span className="text-[10px] uppercase font-bold text-ink-400 block tracking-wider">Suggested queries:</span>
                        <div className="flex flex-wrap gap-1.5">
                          {m.suggestions.map((sug, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleSend(sug)}
                              className="text-[11px] px-2.5 py-1 bg-white hover:bg-forest-50 border border-ink-200 hover:border-forest-600 text-forest-900 rounded-full font-medium transition-colors text-left cursor-pointer"
                            >
                              {sug}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {isUser && (
                    <div className="w-6 h-6 rounded-full bg-ink-700 text-white flex items-center justify-center shrink-0 mt-0.5">
                      <User size={13} />
                    </div>
                  )}
                </div>
              );
            })}

            {loading && (
              <div className="flex gap-2.5 justify-start">
                <div className="w-6 h-6 rounded-full bg-forest-700 text-white flex items-center justify-center shrink-0 mt-0.5 animate-pulse">
                  <Bot size={13} />
                </div>
                <div className="p-3 bg-white border border-ink-100 rounded-xl rounded-bl-none text-ink-500 text-[12px] flex items-center gap-2">
                  <RefreshCw size={13} className="animate-spin text-forest-700" />
                  Querying live PostgreSQL tables...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Default Question Bar */}
          <div className="px-3 py-2 bg-cream-200/50 border-t border-ink-100 flex items-center gap-1.5 overflow-x-auto text-[11px]">
            <span className="text-ink-400 font-semibold uppercase text-[9.5px] shrink-0">Quick:</span>
            {DEFAULT_SUGGESTIONS.slice(0, 3).map((s, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(s)}
                className="whitespace-nowrap px-2 py-0.5 bg-white border border-ink-200 rounded text-ink-700 hover:bg-cream-100 hover:border-forest-600 transition-colors cursor-pointer"
              >
                {s}
              </button>
            ))}
          </div>

          {/* Input Bar */}
          <div className="p-3 bg-white border-t border-ink-100">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about stock, FEFO expiry, POs, alerts..."
                className="flex-1 px-3 py-2 text-[12.5px] border border-ink-200 rounded-lg focus:outline-none focus:border-forest-700 bg-cream-100/30 text-ink-900"
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="px-3 py-2 bg-forest-700 hover:bg-forest-600 text-white rounded-lg transition-colors disabled:opacity-40 cursor-pointer flex items-center justify-center shrink-0"
              >
                <Send size={15} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
