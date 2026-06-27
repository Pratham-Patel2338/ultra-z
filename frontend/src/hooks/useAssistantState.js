import { useMemo, useState } from 'react';
import { sendMessage as apiSendMessage, getMemories, getSettings, updateSettings as apiUpdateSettings } from '../services/api';

const initialMessages = [
  { id: 1, role: 'assistant', text: 'Welcome back, commander. I am ULTRA-Z, ready to assist.', timestamp: '10:00 AM' },
];

const initialMemories = [
  { id: 1, name: 'Aiden', goal: 'Build a smarter assistant', favoriteLanguage: 'Python', likes: 'early morning coding' },
  { id: 2, name: 'Mira', goal: 'Automate daily workflow', favoriteLanguage: 'TypeScript', likes: 'UX design' },
];

const initialSettings = {
  model: 'ollama-ultra-3',
  voice: 'English',
  theme: 'Dark',
  wakewordEnabled: true,
  volume: 80,
  temperature: 0.5,
};

export default function useAssistantState() {
  const [assistantState, setAssistantState] = useState('idle');
  const [messages, setMessages] = useState(initialMessages);
  const [memories, setMemories] = useState(initialMemories);
  const [settings, setSettings] = useState(initialSettings);

  const sendMessage = async (text) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages((prev) => {
      const nextId = prev.length + 1;
      return [...prev, { id: nextId, role: 'user', text, timestamp }];
    });
    setAssistantState('thinking');

    const responseText = await apiSendMessage(text);
    setMessages((prev) => {
      const nextId = prev.length + 1;
      return [...prev, {
        id: nextId,
        role: 'assistant',
        text: responseText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }];
    });
    setAssistantState('speaking');
    window.setTimeout(() => setAssistantState('idle'), 1200);

    return responseText;
  };

  const refreshMemories = async () => {
    try {
      const remoteMemories = await getMemories();
      if (remoteMemories?.length) {
        setMemories(remoteMemories);
      }
    } catch (error) {
      // retain fallback memories
    }
  };

  const refreshSettings = async () => {
    try {
      const remoteSettings = await getSettings();
      setSettings((prev) => ({ ...prev, ...remoteSettings }));
    } catch (error) {
      // keep local defaults
    }
  };

  const updateSettings = async (nextSettings) => {
    setSettings(nextSettings);
    try {
      await apiUpdateSettings(nextSettings);
    } catch (error) {
      // ignore remote failure, keep local state
    }
  };

  const status = useMemo(
    () => ({
      messageCount: messages.length,
      lastState: assistantState,
    }),
    [assistantState, messages.length],
  );

  return {
    assistantState,
    setAssistantState,
    messages,
    memories,
    settings,
    sendMessage,
    refreshMemories,
    refreshSettings,
    updateSettings,
    status,
  };
}
