import { useEffect, useRef, useState } from 'react';
import { client } from '../services/api';

const STATES = {
  IDLE: 'idle',
  LISTENING: 'listening',
  THINKING: 'thinking',
  SPEAKING: 'speaking',
  ERROR: 'error',
};

const EXIT_COMMANDS = ['goodbye', 'exit', 'shutdown', 'stop listening'];
const STT_TIMEOUT_MS = 45000;
const TTS_TIMEOUT_MS = 30000;

const isTimeoutError = (error) => {
  return error?.code === 'ECONNABORTED' || String(error?.message || '').toLowerCase().includes('timeout');
};

const getStatusLabel = (state) => {
  switch (state) {
    case STATES.LISTENING:
      return 'Listening...';
    case STATES.THINKING:
      return 'Thinking...';
    case STATES.SPEAKING:
      return 'Speaking...';
    case STATES.ERROR:
      return 'Error';
    default:
      return 'Ready';
  }
};

export default function useVoiceAssistant() {
  const [assistantState, setAssistantState] = useState(STATES.IDLE);
  const [conversationActive, setConversationActive] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [responseText, setResponseText] = useState('');
  const [error, setError] = useState(null);

  const conversationActiveRef = useRef(conversationActive);
  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const sourceRef = useRef(null);
  const audioElementRef = useRef(null);
  const vadFrameRef = useRef(null);
  const activeAudioUrlRef = useRef(null);
  const pipelineMetricsRef = useRef({
    recording: 0,
    upload: 0,
    conversion: 0,
    stt: 0,
    chatApi: 0,
    llm: 0,
    tts: 0,
    playback: 0,
    total: 0,
  });
  const recordingStartedAtRef = useRef(0);

  useEffect(() => {
    conversationActiveRef.current = conversationActive;
  }, [conversationActive]);

  useEffect(() => {
    return () => {
      stopConversation();
    };
  }, []);

  const clearAudioResources = () => {
    if (vadFrameRef.current) {
      cancelAnimationFrame(vadFrameRef.current);
      vadFrameRef.current = null;
    }

    if (activeAudioUrlRef.current) {
      URL.revokeObjectURL(activeAudioUrlRef.current);
      activeAudioUrlRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch (err) {
        // ignore
      }
      sourceRef.current = null;
    }

    analyserRef.current = null;

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  };

  const stopAudioPlayback = () => {
    const audio = audioElementRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      audioElementRef.current = null;
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  };

  const stopConversation = () => {
    conversationActiveRef.current = false;
    setConversationActive(false);
    setAssistantState(STATES.IDLE);
    stopAudioPlayback();
    stopRecording();
    clearAudioResources();
  };

  const getMicrophoneStream = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      return stream;
    } catch (err) {
      throw new Error('Unable to access microphone. Please check permissions.');
    }
  };

  const createAnalyser = (stream) => {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    audioContextRef.current = audioContext;
    analyserRef.current = analyser;
    sourceRef.current = source;

    return analyser;
  };

  const monitorVoiceActivity = () => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const dataArray = new Float32Array(analyser.fftSize);
    let speechStarted = false;
    let silenceStart = 0;
    const threshold = 0.02;
    const silenceMs = 900;

    const poll = () => {
      analyser.getFloatTimeDomainData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i += 1) {
        sum += dataArray[i] * dataArray[i];
      }

      const rms = Math.sqrt(sum / dataArray.length);
      const isSpeech = rms > threshold;

      if (isSpeech) {
        speechStarted = true;
        silenceStart = 0;
      } else if (speechStarted) {
        if (!silenceStart) {
          silenceStart = performance.now();
        } else if (performance.now() - silenceStart > silenceMs) {
          stopRecording();
          return;
        }
      }

      if (conversationActiveRef.current && mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        vadFrameRef.current = requestAnimationFrame(poll);
      }
    };

    vadFrameRef.current = requestAnimationFrame(poll);
  };

  const logPipelineMetrics = (metrics) => {
    const values = [
      ['Recording', `${(metrics.recording / 1000).toFixed(2)}s`],
      ['Upload', `${metrics.upload.toFixed(0)}ms`],
      ['Conversion', `${metrics.conversion.toFixed(0)}ms`],
      ['STT', `${metrics.stt.toFixed(0)}ms`],
      ['Chat', `${metrics.chatApi.toFixed(0)}ms`],
      ['LLM', `${metrics.llm.toFixed(0)}ms`],
      ['TTS', `${metrics.tts.toFixed(0)}ms`],
      ['Playback', `${metrics.playback.toFixed(0)}ms`],
      ['TOTAL', `${metrics.total.toFixed(0)}ms`],
    ];

    const line = values.map(([label, value]) => `${label.padEnd(12)}${value}`).join('');
    console.info('==============================VOICE PIPELINE');
    console.info(line);
    console.info('==============================');
  };

  const transcribeAudio = async (blob) => {
    const form = new FormData();
    form.append('audio', blob, 'recording.webm');

    const start = performance.now();
    try {
      const response = await client.post('/api/v1/voice/transcribe', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: STT_TIMEOUT_MS,
      });
      pipelineMetricsRef.current.upload = performance.now() - start;
      return response.data?.transcript || '';
    } catch (error) {
      if (isTimeoutError(error)) {
        throw new Error('STT_TIMEOUT');
      }
      throw error;
    }
  };

  const sendChat = async (message, onDelta) => {
    const start = performance.now();
    const token = localStorage.getItem('ultra_z_token');
    const response = await fetch(`${client.defaults.baseURL}/api/v1/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      throw new Error(`Streaming chat failed with ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';

    if (!reader) {
      throw new Error('Streaming response body unavailable');
    }

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        const trimmed = part.trim();
        if (!trimmed.startsWith('data:')) continue;
        const payload = trimmed.slice(5).trim();
        if (payload === '[DONE]') {
          break;
        }
        try {
          const event = JSON.parse(payload);
          if (event.delta) {
            fullText += event.delta;
            onDelta?.(fullText, event.delta);
          }
        } catch (err) {
          console.warn('Unable to parse stream payload', err);
        }
      }
    }

    pipelineMetricsRef.current.chatApi = performance.now() - start;
    return fullText;
  };

  const requestTTS = async (text) => {
    const start = performance.now();
    try {
      const response = await client.post(
        '/api/v1/voice/speak',
        { text, voice: 'auto', language: 'auto' },
        { responseType: 'arraybuffer', timeout: TTS_TIMEOUT_MS },
      );
      pipelineMetricsRef.current.tts = performance.now() - start;
      return new Blob([response.data], { type: 'audio/wav' });
    } catch (error) {
      if (isTimeoutError(error)) {
        throw new Error('TTS_TIMEOUT');
      }
      throw error;
    }
  };

  const playAudioBlob = async (blob) => {
    const audioUrl = URL.createObjectURL(blob);
    activeAudioUrlRef.current = audioUrl;
    const audio = new Audio(audioUrl);
    audioElementRef.current = audio;

    const cleanupPlayback = () => {
      if (activeAudioUrlRef.current === audioUrl) {
        URL.revokeObjectURL(audioUrl);
        activeAudioUrlRef.current = null;
      }
      audioElementRef.current = null;
    };

    audio.addEventListener('ended', () => {
      cleanupPlayback();
      if (conversationActiveRef.current) {
        void startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
    });

    audio.addEventListener('error', () => {
      cleanupPlayback();
      if (conversationActiveRef.current) {
        void startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
    });

    try {
      const playbackStart = performance.now();
      await audio.play();
      pipelineMetricsRef.current.playback = performance.now() - playbackStart;
    } catch (err) {
      cleanupPlayback();
      console.warn('Audio playback failed', err);
      setError('Unable to play assistant voice.');
      if (conversationActiveRef.current) {
        void startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
    }
  };

  const handleRecordingComplete = async (blob) => {
    if (!conversationActiveRef.current) {
      return;
    }

    const pipelineStart = performance.now();
    pipelineMetricsRef.current = {
      recording: 0,
      upload: 0,
      conversion: 0,
      stt: 0,
      chatApi: 0,
      llm: 0,
      tts: 0,
      playback: 0,
      total: 0,
    };

    setAssistantState(STATES.THINKING);
    setError(null);

    try {
      const transcriptText = await transcribeAudio(blob);
      if (!conversationActiveRef.current) {
        return;
      }

      if (!transcriptText.trim()) {
        setError('No speech detected. Listening again.');
        setAssistantState(STATES.LISTENING);
        if (conversationActiveRef.current) {
          await startListeningCycle();
        }
        return;
      }

      setTranscript(transcriptText);

      if (EXIT_COMMANDS.includes(transcriptText.trim().toLowerCase())) {
        const goodbyeText = 'Goodbye.';
        setResponseText(goodbyeText);
        setAssistantState(STATES.SPEAKING);
        const goodbyeAudio = await requestTTS(goodbyeText);
        stopConversation();
        await playAudioBlob(goodbyeAudio);
        return;
      }

      let assistantMessage = '';
      await sendChat(transcriptText, (partialText) => {
        assistantMessage = partialText;
        setResponseText(partialText);
      });
      if (!conversationActiveRef.current) {
        return;
      }

      setResponseText(assistantMessage || 'I am listening.');
      setAssistantState(STATES.SPEAKING);
      const ttsAudio = await requestTTS(assistantMessage || 'I am listening.');
      await playAudioBlob(ttsAudio);
    } catch (err) {
      console.error('Conversation loop failed', err);
      if (err?.message === 'STT_TIMEOUT') {
        setError('Speech recognition took too long. Please try again.');
      } else if (err?.message === 'TTS_TIMEOUT') {
        setError('Speech synthesis took too long. Please try again.');
      } else {
        setError('The assistant had trouble processing that.');
      }
      if (conversationActiveRef.current) {
        setAssistantState(STATES.LISTENING);
        await startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
    } finally {
      pipelineMetricsRef.current.total = performance.now() - pipelineStart;
      if (pipelineMetricsRef.current.recording === 0) {
        pipelineMetricsRef.current.recording = performance.now() - recordingStartedAtRef.current;
      }
      logPipelineMetrics(pipelineMetricsRef.current);
    }
  };

  const startListeningCycle = async () => {
    if (!conversationActiveRef.current) {
      return;
    }

    clearAudioResources();
    setError(null);
    setAssistantState(STATES.LISTENING);
    setRecording(true);
    recordingStartedAtRef.current = performance.now();

    try {
      const stream = await getMicrophoneStream();
      createAnalyser(stream);

      const recorder = new MediaRecorder(stream);
      const chunks = [];

      recorder.addEventListener('dataavailable', (event) => {
        if (event.data && event.data.size) {
          chunks.push(event.data);
        }
      });

      recorder.addEventListener('stop', async () => {
        pipelineMetricsRef.current.recording = performance.now() - recordingStartedAtRef.current;
        setRecording(false);
        clearAudioResources();
        if (!conversationActiveRef.current) {
          return;
        }

        const blob = new Blob(chunks, { type: 'audio/webm' });
        await handleRecordingComplete(blob);
      });

      mediaRecorderRef.current = recorder;
      recorder.start();
      monitorVoiceActivity();
    } catch (err) {
      console.error('Microphone capture failed', err);
      setError('Unable to access microphone.');
      setAssistantState(STATES.ERROR);
      setRecording(false);
    }
  };

  const toggleConversation = async () => {
    if (conversationActiveRef.current) {
      stopConversation();
      return;
    }

    conversationActiveRef.current = true;
    setConversationActive(true);
    setTranscript('');
    setResponseText('');
    setError(null);
    await startListeningCycle();
  };

  return {
    assistantState,
    STATES,
    conversationActive,
    recording,
    transcript,
    responseText,
    error,
    statusLabel: getStatusLabel(assistantState),
    toggleConversation,
  };
}
