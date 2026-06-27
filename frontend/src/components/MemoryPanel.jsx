export default function MemoryPanel({ memories, onRefresh }) {
  return (
    <div className="glass-panel space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-xl font-semibold text-white">Memory Panel</h3>
          <p className="text-sm text-slate-400">Stored user preferences and goals.</p>
        </div>
        <button onClick={onRefresh} type="button" className="rounded-3xl bg-slate-900/70 px-4 py-3 text-sm text-slate-100 transition hover:bg-slate-800/90">
          Refresh
        </button>
      </div>

      <div className="grid gap-4">
        {memories.map((memory) => (
          <div key={memory.id} className="rounded-[28px] border border-white/10 bg-slate-950/75 p-4 shadow-[0_18px_40px_rgba(14,165,233,0.12)]">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-lg font-semibold text-slate-100">{memory.name}</h4>
              <span className="rounded-full bg-sky-500/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-sky-200">Memory</span>
            </div>
            <div className="mt-3 grid gap-2 text-sm text-slate-300">
              <p><span className="font-semibold text-slate-100">Goal:</span> {memory.goal}</p>
              <p><span className="font-semibold text-slate-100">Favorite Language:</span> {memory.favoriteLanguage}</p>
              <p><span className="font-semibold text-slate-100">Likes:</span> {memory.likes}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
