import React from 'react';
import { motion } from 'framer-motion';

const stateStyles = {
  idle: {
    scale: 0.98,
    glow: 'rgba(148,163,184,0.14)',
    ring: 'rgba(148,163,184,0.08)',
    main: 'from-slate-900/60 to-slate-900/25',
  },
  listening: {
    scale: 1.02,
    glow: 'rgba(56,189,248,0.32)',
    ring: 'rgba(56,189,248,0.25)',
    main: 'from-sky-500/25 to-cyan-500/15',
  },
  thinking: {
    scale: 1.03,
    glow: 'rgba(168,85,247,0.3)',
    ring: 'rgba(168,85,247,0.22)',
    main: 'from-violet-500/25 to-indigo-600/15',
  },
  speaking: {
    scale: 1.08,
    glow: 'rgba(34,211,238,0.3)',
    ring: 'rgba(34,211,238,0.25)',
    main: 'from-cyan-500/25 to-sky-500/15',
  },
  error: {
    scale: 1.01,
    glow: 'rgba(248,113,113,0.32)',
    ring: 'rgba(248,113,113,0.22)',
    main: 'from-rose-500/25 to-red-500/15',
  },
};

export default function VoiceOrb({ state = 'idle' }) {
  const styles = stateStyles[state] || stateStyles.idle;

  return (
    <div className="relative w-[320px] h-[320px] flex items-center justify-center">
      <motion.div
        initial={{ scale: 0.96, x: 0 }}
        animate={{
          scale: styles.scale,
          x: state === 'error' ? [0, -8, 8, 0] : 0,
        }}
        transition={{ duration: state === 'error' ? 0.5 : 1.2, repeat: state === 'error' ? Infinity : Infinity, repeatType: 'reverse', ease: 'easeInOut' }}
        className="relative rounded-full flex items-center justify-center"
        style={{ boxShadow: `0 0 90px ${styles.glow}` }}
      >
        <div className="absolute inset-0 rounded-full bg-black/40" />

        <motion.div
          animate={{ rotate: state === 'thinking' ? 360 : 0 }}
          transition={{ duration: state === 'thinking' ? 6 : 0, ease: 'linear', repeat: state === 'thinking' ? Infinity : 0 }}
          className="relative rounded-full flex items-center justify-center"
          style={{ width: 240, height: 240 }}
        >
          <div className={`absolute inset-0 rounded-full bg-gradient-to-br ${styles.main} opacity-90`} />
          <div className="relative w-[140px] h-[140px] rounded-full bg-black/70 border border-white/10 flex items-center justify-center text-white font-semibold tracking-[0.15em] text-sm">
            ULTRA-Z
          </div>
        </motion.div>

        <div className="absolute inset-0 rounded-full border border-white/10" />
        <div className="absolute inset-8 rounded-full border border-white/5" />
        <div className="absolute inset-16 rounded-full border border-white/5" />

        {state === 'speaking' && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            {Array.from({ length: 7 }).map((_, index) => (
              <motion.span
                key={index}
                className="absolute bottom-10 w-2 rounded-full bg-cyan-400/80"
                style={{ left: `${50 + (index - 3) * 8}%`, height: 40 }}
                animate={{ scaleY: [1, 2.2, 1] }}
                transition={{ duration: 0.7, repeat: Infinity, delay: index * 0.08, ease: 'easeInOut' }}
              />
            ))}
          </div>
        )}

        <div
          className="absolute inset-0 rounded-full"
          style={{ boxShadow: `0 0 60px ${styles.ring}` }}
        />
      </motion.div>
    </div>
  );
}
