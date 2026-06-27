import React from 'react';

const STATUS_LABELS = {
  idle: 'Ready',
  listening: 'Listening...',
  thinking: 'Thinking...',
  speaking: 'Speaking...',
  error: 'Error',
};

export default function AssistantState({ state, transcript, response }) {
  return (
    <div className="mt-6 w-full max-w-2xl px-6 py-5 bg-white/5 border border-slate-200/5 rounded-3xl backdrop-blur-xl shadow-[0_0_80px_rgba(14,165,233,0.08)]">
      <div className="flex items-center justify-center gap-3 text-sm uppercase tracking-[0.3em] text-slate-100 mb-4">
        <span className="inline-flex h-3 w-3 rounded-full bg-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.4)]" />
        {STATUS_LABELS[state] || 'Ready'}
      </div>

      <div className="space-y-4 text-left text-slate-200">
        {transcript ? (
          <div className="rounded-2xl bg-white/5 border border-cyan-400/10 p-4">
            <div className="text-xs uppercase tracking-[0.25em] text-cyan-200/80 mb-2">You</div>
            <div className="text-base text-white">{transcript}</div>
          </div>
        ) : null}

        {response ? (
          <div className="rounded-2xl bg-white/5 border border-indigo-400/10 p-4">
            <div className="text-xs uppercase tracking-[0.25em] text-indigo-200/80 mb-2">Ultra-Z</div>
            <div className="text-base text-white">{response}</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
