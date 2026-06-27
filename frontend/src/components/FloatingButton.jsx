import { useRef, useState } from 'react';

export default function FloatingButton({ onClick }) {
  const buttonRef = useRef(null);
  const [position, setPosition] = useState({ right: 24, bottom: 24 });
  const pointerData = useRef({ x: 0, y: 0, dragging: false });

  const startDrag = (event) => {
    pointerData.current = {
      x: event.clientX,
      y: event.clientY,
      dragging: true,
    };
    document.addEventListener('pointermove', onDrag);
    document.addEventListener('pointerup', stopDrag);
  };

  const onDrag = (event) => {
    if (!pointerData.current.dragging) return;
    const dx = event.clientX - pointerData.current.x;
    const dy = event.clientY - pointerData.current.y;
    pointerData.current.x = event.clientX;
    pointerData.current.y = event.clientY;
    setPosition((prev) => ({
      right: Math.max(16, prev.right - dx),
      bottom: Math.max(16, prev.bottom - dy),
    }));
  };

  const stopDrag = () => {
    pointerData.current.dragging = false;
    document.removeEventListener('pointermove', onDrag);
    document.removeEventListener('pointerup', stopDrag);
  };

  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={onClick}
      onPointerDown={startDrag}
      style={{ right: position.right, bottom: position.bottom }}
      className="fixed z-50 flex h-16 w-16 items-center justify-center rounded-full border border-white/15 bg-slate-950/95 text-slate-100 shadow-[0_26px_64px_rgba(0,0,0,0.45)] backdrop-blur-xl hover:bg-slate-900"
      title="Open ULTRA-Z"
    >
      <span className="text-2xl">🤖</span>
    </button>
  );
}
