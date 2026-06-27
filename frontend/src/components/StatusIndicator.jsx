export default function StatusIndicator({ state, label }) {
  const tone = state === 'speaking' ? 'from-fuchsia-500 to-cyan-400' : state === 'thinking' ? 'from-sky-400 to-indigo-500' : 'from-slate-400 to-slate-500';
  return (
    <div className="inline-flex items-center gap-3 rounded-3xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-200 shadow-[0_0_40px_rgba(14,165,233,0.12)]">
      <span className={`inline-flex h-3 w-3 rounded-full bg-gradient-to-r ${tone}`} />
      <span>{label}</span>
    </div>
  );
}
