import { useEffect, useRef, useState } from 'react';

const WS_URL = 'ws://127.0.0.1:8000/ws';
const HEALTH_URL = 'http://127.0.0.1:8000/health';

async function checkBackendHealth() {
  try {
    const response = await fetch(HEALTH_URL, { cache: 'no-store' });
    return response.ok;
  } catch (error) {
    return false;
  }
}

export default function useWebSocket(onStateUpdate) {
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef(null);
  const socketRef = useRef(null);
  const callbackRef = useRef(onStateUpdate);

  useEffect(() => {
    callbackRef.current = onStateUpdate;
  }, [onStateUpdate]);

  useEffect(() => {
    let canceled = false;
    const closeIntentionalRef = { current: false };

    async function updateHealthStatus() {
      const online = await checkBackendHealth();
      if (!canceled) {
        setConnected(online);
      }
    }

    function connect() {
      if (reconnectTimer.current) {
        window.clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }

      if (socketRef.current) {
        closeIntentionalRef.current = true;
        socketRef.current.close();
      }

      closeIntentionalRef.current = false;
      const ws = new WebSocket(WS_URL);
      socketRef.current = ws;

      ws.addEventListener('open', () => {
        setConnected(true);
      });

      ws.addEventListener('message', (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.state) {
            callbackRef.current(payload.state);
          }
        } catch (error) {
          console.warn('Invalid WebSocket payload', error);
        }
      });

      ws.addEventListener('close', async () => {
        if (canceled || closeIntentionalRef.current) {
          return;
        }

        setConnected(false);
        await updateHealthStatus();
        reconnectTimer.current = window.setTimeout(connect, 3000);
      });

      ws.addEventListener('error', async () => {
        if (canceled || closeIntentionalRef.current) {
          return;
        }

        setConnected(false);
        ws.close();
        await updateHealthStatus();
      });
    }

    updateHealthStatus();
    connect();

    return () => {
      canceled = true;
      if (reconnectTimer.current) {
        window.clearTimeout(reconnectTimer.current);
      }
      if (socketRef.current) {
        closeIntentionalRef.current = true;
        socketRef.current.close();
      }
    };
  }, []);

  return { connected };
}
