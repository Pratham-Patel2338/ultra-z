import { useMemo, useState } from 'react';

export default function ConversationPanel({ messages, onSendMessage, assistantState }) {
  const [draft, setDraft] = useState('');

  const visibleMessages = useMemo(() => messages.slice(-12), [messages]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!draft.trim()) return;
    await onSendMessage(draft.trim());
    setDraft('');
  };

  return (
    <div className="glass-panel flex h-full min-h-[520px] flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-xl font-semibold text-white">Conversation</h3>
          <p className="text-sm text-slate-400">Last activity: {assistantState}</p>
        </div>
        <div className="rounded-3xl bg-slate-900/70 px-4 py-3 text-sm text-slate-300">Auto mode enabled</div>
      </div>

      <div className="message-scroll flex-1 space-y-4 overflow-y-auto rounded-[28px] border border-white/10 bg-slate-950/70 p-4">
        {visibleMessages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[78%] rounded-3xl px-5 py-4 text-sm shadow-[0_18px_40px_rgba(0,0,0,0.18)] ${message.role === 'user' ? 'bg-sky-500/15 text-slate-100' : 'bg-slate-900/80 text-slate-200'}`}>
              <div className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-500">{message.role === 'user' ? 'You' : 'Ultra-Z'}</div>
              <p>{message.text}</p>
              <div className="mt-3 text-right text-[11px] uppercase tracking-[0.2em] text-slate-500">{message.timestamp}</div>
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-3 rounded-[28px] border border-white/10 bg-slate-950/70 p-3">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask Ultra-Z a question..."
          className="flex-1 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              handleSubmit(event);
            }
          }}
        />
        <button type="submit" className="rounded-3xl bg-sky-400/15 px-4 py-3 text-sm text-sky-200 transition hover:bg-sky-400/25">
          Send
        </button>
      </form>
    </div>
  );
}
