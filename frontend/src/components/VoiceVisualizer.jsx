import { useMemo } from 'react';

const BAR_COUNT = 12;

export default function VoiceVisualizer({ active }) {
  const bars = useMemo(() => Array.from({ length: BAR_COUNT }, (_, index) => index), []);

  return (
    <div className="voice-bars relative mx-auto flex h-28 w-full items-end justify-between gap-2 rounded-[28px] border border-white/10 bg-slate-950/50 p-4">
      {bars.map((bar) => (
        <div
          key={bar}
          className={`h-8 w-2 rounded-full bg-gradient-to-t from-sky-400 to-cyan-200 ${active ? `animate-pulse-slow` : 'opacity-40'}`}
          style={{ animationDelay: `${bar * 80}ms` }}
        />
      ))}
    </div>
  );
}
