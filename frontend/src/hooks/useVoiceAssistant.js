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
    setRecording(false);
  };

  const stopConversation = () => {
    conversationActiveRef.current = false;
    setConversationActive(false);
    setAssistantState(STATES.IDLE);
    setRecording(false);
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

  const transcribeAudio = async (blob) => {
    const form = new FormData();
    form.append('audio', blob, 'recording.webm');

    const response = await client.post('/api/v1/voice/transcribe', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    return response.data?.transcript || '';
  };

  const sendChat = async (message) => {
    const response = await client.post('/api/v1/chat', { message });
    return response.data?.assistant_message?.content || response.data?.response || '';
  };

  const requestTTS = async (text) => {
    const response = await client.post(
      '/api/v1/voice/speak',
      { text, voice: 'auto', language: 'auto' },
      { responseType: 'arraybuffer' },
    );

    return new Blob([response.data], { type: 'audio/wav' });
  };

  const playAudioBlob = async (blob) => {
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);
    audioElementRef.current = audio;

    audio.addEventListener('ended', async () => {
      URL.revokeObjectURL(audioUrl);
      audioElementRef.current = null;

      if (conversationActiveRef.current) {
        await startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
    });

    audio.addEventListener('error', async () => {
      URL.revokeObjectURL(audioUrl);
      audioElementRef.current = null;
      if (conversationActiveRef.current) {
        await startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
    });

    try {
      await audio.play();
    } catch (err) {
      console.warn('Audio playback failed', err);
      setError('Unable to play assistant voice.');
      if (conversationActiveRef.current) {
        await startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
    }
  };

  const handleRecordingComplete = async (blob) => {
    if (!conversationActiveRef.current) {
      return;
    }

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

      const assistantMessage = await sendChat(transcriptText);
      if (!conversationActiveRef.current) {
        return;
      }

      setResponseText(assistantMessage);
      setAssistantState(STATES.SPEAKING);
      const ttsAudio = await requestTTS(assistantMessage || 'I am listening.');
      await playAudioBlob(ttsAudio);
    } catch (err) {
      console.error('Conversation loop failed', err);
      setError('The assistant had trouble processing that.');
      if (conversationActiveRef.current) {
        setAssistantState(STATES.LISTENING);
        await startListeningCycle();
      } else {
        setAssistantState(STATES.IDLE);
      }
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
