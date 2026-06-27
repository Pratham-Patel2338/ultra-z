const WS_URL = 'ws://127.0.0.1:8000/ws';

export function createAssistantWebSocket({ onOpen, onMessage, onClose, onError }) {
  const ws = new WebSocket(WS_URL);

  ws.addEventListener('open', () => {
    onOpen?.();
  });

  ws.addEventListener('message', (event) => {
    try {
      const payload = JSON.parse(event.data);
      onMessage?.(payload);
    } catch (error) {
      console.warn('Invalid websocket payload', error);
    }
  });

  ws.addEventListener('close', () => {
    onClose?.();
  });

  ws.addEventListener('error', (error) => {
    onError?.(error);
  });

  return ws;
}
