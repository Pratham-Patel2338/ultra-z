import { motion } from 'framer-motion';

export default function TopBar({ title, subtitle, onMinimize, connected }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between gap-4 rounded-[28px] border border-white/10 bg-slate-950/40 p-5 shadow-neon"
    >
      <div>
        <div className="text-sm uppercase tracking-[0.35em] text-sky-200/60">{title}</div>
        <h1 className="mt-2 text-3xl font-semibold text-white">{subtitle}</h1>
      </div>
      <div className="flex items-center gap-3">
        <span className={`inline-flex items-center rounded-2xl border border-white/10 px-3 py-2 text-sm ${connected ? 'bg-slate-900/70 text-sky-300' : 'bg-rose-950/70 text-rose-300'}`}>{connected ? 'ONLINE' : 'OFFLINE'}</span>
        <button
          type="button"
          onClick={onMinimize}
          className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-100 transition hover:bg-white/10"
        >
          <span className="text-xl">—</span>
        </button>
      </div>
    </motion.div>
  );
}
