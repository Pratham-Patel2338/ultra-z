import { motion } from 'framer-motion';

const navItems = [
  { key: 'home', label: 'Chat', icon: '💬' },
  { key: 'memory', label: 'Memory', icon: '🧠' },
  { key: 'settings', label: 'Settings', icon: '⚙️' },
  { key: 'history', label: 'History', icon: '📜' },
];

export default function SideBar({ activeView, onChangeView, collapsed, onToggleCollapse, connected }) {
  return (
    <motion.aside
      initial={{ opacity: 0, x: -24 }}
      animate={{ opacity: 1, x: 0 }}
      className="glass-panel flex min-h-full flex-col gap-6 p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-slate-50">
          <div className="flex h-12 w-12 items-center justify-center rounded-3xl border border-white/10 bg-slate-900/70 text-2xl shadow-neon">⚡</div>
          {!collapsed && (
            <div>
              <p className="text-sm uppercase tracking-[0.35em] text-sky-300/90">ULTRA-Z</p>
              <p className="text-xs text-slate-400">Jarvis-style assistant</p>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="inline-flex h-12 w-12 items-center justify-center rounded-3xl border border-white/10 bg-white/5 text-slate-100"
        >
          {collapsed ? '→' : '←'}
        </button>
      </div>

      <div className="space-y-2">
        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => onChangeView(item.key)}
            className={`group flex w-full items-center gap-3 rounded-3xl px-4 py-3 text-left transition ${activeView === item.key ? 'bg-sky-400/10 text-sky-300' : 'bg-white/5 text-slate-300 hover:bg-white/10'}`}
          >
            <span className="text-xl">{item.icon}</span>
            {!collapsed && <span className="font-medium">{item.label}</span>}
          </button>
        ))}
      </div>

      <div className="mt-auto rounded-3xl border border-white/10 bg-slate-900/80 p-4 text-sm text-slate-300">
        <p className="font-semibold text-slate-100">Status</p>
        <p className="mt-2">{connected ? 'Live connection active' : 'Offline mode'}</p>
      </div>
    </motion.aside>
  );
}
