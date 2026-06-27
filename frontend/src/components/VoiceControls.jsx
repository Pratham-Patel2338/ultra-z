import React from 'react';
import { motion } from 'framer-motion';

export default function VoiceControls({ conversationActive, toggleConversation, statusLabel }) {
  return (
    <div className="flex flex-col items-center mt-8">
      <motion.button
        onClick={toggleConversation}
        whileTap={{ scale: 0.95 }}
        className="relative w-36 h-36 rounded-full flex items-center justify-center bg-slate-900/70 border border-cyan-400/20 shadow-[0_0_40px_rgba(56,189,248,0.25)]"
      >
        <div className="absolute inset-0 rounded-full bg-gradient-to-br from-cyan-500/20 via-sky-500/10 to-transparent" />
        <div className="relative z-10 w-28 h-28 rounded-full bg-cyan-600 shadow-2xl shadow-cyan-500/30 flex items-center justify-center text-white text-center font-semibold px-3">
          {conversationActive ? 'End Conversation' : 'Start Conversation'}
        </div>
      </motion.button>
      <div className="mt-4 text-sm text-slate-300">{conversationActive ? statusLabel : 'Tap once to begin'} </div>
    </div>
  );
}
