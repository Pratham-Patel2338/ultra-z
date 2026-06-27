import { motion } from 'framer-motion';

const stateStyles = {
  idle: { from: '#0ea5e9', to: '#0f172a', effect: 'glow' },
  listening: { from: '#38bdf8', to: '#0f172a', effect: 'pulse' },
  thinking: { from: '#93c5fd', to: '#0f172a', effect: 'rotate' },
  speaking: { from: '#60a5fa', to: '#0f172a', effect: 'wave' },
};

export default function ArcReactor({ state }) {
  const style = stateStyles[state] || stateStyles.idle;

  return (
    <motion.div
      animate={{ rotate: style.effect === 'rotate' ? 360 : 0 }}
      transition={{ duration: style.effect === 'rotate' ? 12 : 0, repeat: Infinity, ease: 'linear' }}
      className="relative flex h-[320px] w-[320px] items-center justify-center rounded-full border border-white/10 bg-slate-950/40 shadow-[0_0_80px_rgba(14,165,233,0.18)]"
    >
      <div className="absolute inset-0 rounded-full bg-gradient-radial from-sky-400/20 via-transparent to-transparent" />
      <div className="absolute inset-0 rounded-full border border-sky-400/20" />
      <div className="absolute inset-12 rounded-full border border-sky-400/15 backdrop-blur-sm" />
      <div className="absolute inset-24 rounded-full border border-sky-300/20 bg-slate-950/30" />
      <div className="relative flex h-28 w-28 items-center justify-center rounded-full bg-slate-950/90 text-lg text-slate-100 shadow-[inset_0_0_40px_rgba(14,165,233,0.4)]">
        <span className="text-xl font-semibold tracking-[0.26em]">ULTRA-Z</span>
      </div>

      {style.effect === 'pulse' && (
        <motion.div
          className="absolute inset-0 rounded-full border border-sky-300/20"
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}

      {style.effect === 'wave' && (
        <motion.div
          className="absolute inset-0 rounded-full border border-sky-300/10"
          animate={{ opacity: [0.7, 0.2, 0.7], scale: [1, 1.05, 1] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
    </motion.div>
  );
}
