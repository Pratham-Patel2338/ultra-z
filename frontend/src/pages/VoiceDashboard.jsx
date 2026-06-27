import React from 'react';
import VoiceOrb from '../components/VoiceOrb';
import VoiceControls from '../components/VoiceControls';
import AssistantState from '../components/AssistantState';
import ConnectionStatus from '../components/ConnectionStatus';
import useVoiceAssistant from '../hooks/useVoiceAssistant';

export default function VoiceDashboard() {
  const {
    assistantState,
    conversationActive,
    transcript,
    responseText,
    error,
    statusLabel,
    toggleConversation,
  } = useVoiceAssistant();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.16),_transparent_25%),linear-gradient(to_bottom,_#020617,_#030615)] text-white flex flex-col items-center justify-start">
      <div className="w-full max-w-6xl p-6">
        <div className="flex items-center justify-between">
          <ConnectionStatus />
        </div>
      </div>

      <main className="flex-1 flex flex-col items-center justify-center px-4 py-8 gap-8">
        <VoiceOrb state={assistantState} />
        <AssistantState state={assistantState} transcript={transcript} response={responseText} />
        <VoiceControls conversationActive={conversationActive} toggleConversation={toggleConversation} statusLabel={statusLabel} />

        {error && <div className="mt-4 text-rose-400 text-sm">{error}</div>}
      </main>

      <div className="fixed left-4 top-1/2 -translate-y-1/2 w-60 p-3 bg-white/5 rounded-3xl backdrop-blur-xl hidden md:block">
        <div className="text-sm font-semibold mb-2 text-slate-100">Controls</div>
        <div className="text-xs text-slate-400">Memories · Settings · System Status (panel hidden by default)</div>
      </div>
    </div>
  );
}
