import { useCallback, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import useAssistantState from './hooks/useAssistantState';
import useWebSocket from './hooks/useWebSocket';
import TopBar from './components/TopBar';
import SideBar from './components/SideBar';
import ArcReactor from './components/ArcReactor';
import VoiceVisualizer from './components/VoiceVisualizer';
import ConversationPanel from './components/ConversationPanel';
import StatusIndicator from './components/StatusIndicator';
import MemoryPanel from './components/MemoryPanel';
import SettingsPanel from './components/SettingsPanel';
import FloatingButton from './components/FloatingButton';

const VIEW_CONFIG = {
  home: { title: 'Home', subtitle: 'Real-time voice assistant control center' },
  memory: { title: 'Memory', subtitle: 'Review stored user insights and goals' },
  settings: { title: 'Settings', subtitle: 'Customize ULTRA-Z and voice behavior' },
  history: { title: 'History', subtitle: 'Conversation history and interaction logs' },
};

export default function App() {
  const [activeView, setActiveView] = useState('home');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const {
    assistantState,
    messages,
    memories,
    settings,
    sendMessage,
    updateSettings,
    refreshMemories,
    refreshSettings,
    setAssistantState,
  } = useAssistantState();

  const handleStateUpdate = useCallback((state) => {
    setAssistantState(state);
  }, []);

  const { connected } = useWebSocket(handleStateUpdate);

  const activeLabel = useMemo(() => {
    if (assistantState === 'listening') return '🎤 Listening';
    if (assistantState === 'thinking') return '🧠 Thinking';
    if (assistantState === 'speaking') return '🔊 Speaking';
    return 'Idle';
  }, [assistantState]);

  return (
    <div className="relative min-h-screen bg-[#050816] text-slate-100 overflow-hidden">
      {isMinimized && (
        <FloatingButton onClick={() => setIsMinimized(false)} />
      )}

      <AnimatePresence>
        {!isMinimized && (
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
            className="grid h-screen grid-cols-1 xl:grid-cols-[280px_1fr] gap-4 p-4 xl:p-6"
          >
            <SideBar
              activeView={activeView}
              onChangeView={setActiveView}
              collapsed={sidebarCollapsed}
              onToggleCollapse={() => setSidebarCollapsed((value) => !value)}
              connected={connected}
            />

            <main className="flex flex-col gap-4 overflow-hidden rounded-[32px] border border-white/10 bg-white/5 p-4 shadow-neon backdrop-blur-xl">
              <TopBar
                title="ULTRA-Z"
                subtitle={VIEW_CONFIG[activeView]?.subtitle}
                onMinimize={() => setIsMinimized(true)}
                connected={connected}
              />

              <div className="grid flex-1 grid-cols-1 gap-4 xl:grid-cols-[1.15fr_0.85fr]">
                <section className="space-y-4">
                  <div className="glass-panel grid gap-4 p-5">
                    <div className="flex flex-col items-center justify-center gap-4 text-center">
                      <h2 className="text-2xl font-semibold tracking-[0.18em] text-slate-100">ULTRA-Z Reactor</h2>
                      <p className="text-sm text-slate-400">Futuristic state monitoring with voice reaction visuals.</p>
                    </div>

                    <div className="flex flex-col items-center gap-6 rounded-[28px] border border-white/10 bg-slate-950/30 p-6 shadow-[0_0_80px_rgba(14,165,233,0.18)]">
                      <ArcReactor state={assistantState} />
                      <StatusIndicator state={assistantState} label={activeLabel} />
                      <VoiceVisualizer active={assistantState === 'listening' || assistantState === 'speaking'} />
                    </div>
                  </div>

                  <ConversationPanel
                    messages={messages}
                    onSendMessage={sendMessage}
                    assistantState={assistantState}
                  />
                </section>

                <aside className="space-y-4">
                  <div className="glass-panel p-5">
                    <h3 className="mb-4 text-lg font-semibold tracking-wide text-slate-100">Live Status</h3>
                    <div className="space-y-3 text-sm text-slate-300">
                      <div className="flex items-center justify-between rounded-2xl bg-slate-900/70 p-4">
                        <span>Backend</span>
                        <span className={connected ? 'text-sky-400' : 'text-rose-400'}>{connected ? 'Connected' : 'Disconnected'}</span>
                      </div>
                      <div className="flex items-center justify-between rounded-2xl bg-slate-900/70 p-4">
                        <span>Messages</span>
                        <span>{messages.length}</span>
                      </div>
                      <div className="flex items-center justify-between rounded-2xl bg-slate-900/70 p-4">
                        <span>Voice Mode</span>
                        <span className="text-sky-300">Realtime</span>
                      </div>
                    </div>
                  </div>

                  <MemoryPanel memories={memories} onRefresh={refreshMemories} />
                </aside>
              </div>

              {activeView === 'settings' && (
                <div className="glass-panel rounded-[28px] border border-white/10 p-5 shadow-[0_0_120px_rgba(14,165,233,0.1)]">
                  <SettingsPanel settings={settings} onUpdateSettings={updateSettings} onRefresh={refreshSettings} />
                </div>
              )}
              {activeView === 'memory' && (
                <div className="glass-panel rounded-[28px] border border-white/10 p-5 shadow-[0_0_120px_rgba(14,165,233,0.1)]">
                  <MemoryPanel memories={memories} onRefresh={refreshMemories} />
                </div>
              )}
              {activeView === 'history' && (
                <div className="glass-panel rounded-[28px] border border-white/10 p-5 shadow-[0_0_120px_rgba(14,165,233,0.1)]">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xl font-semibold text-white">Interaction History</h3>
                        <p className="text-sm text-slate-400">Recent voice and chat sessions.</p>
                      </div>
                      <button type="button" className="btn primary-btn">Refresh</button>
                    </div>
                    <div className="grid gap-3">
                      <div className="rounded-3xl bg-slate-950/70 p-4 text-slate-300">No history is available yet. Start a conversation to populate interactions.</div>
                    </div>
                  </div>
                </div>
              )}
            </main>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
