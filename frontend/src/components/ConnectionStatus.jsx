import React, { useEffect, useState } from 'react';
import { getStatus } from '../services/api';

export default function ConnectionStatus() {
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function check() {
      try {
        const res = await getStatus();
        if (!mounted) return;
        setOnline(res?.online === true);
      } catch (err) {
        if (!mounted) return;
        setOnline(false);
      }
    }
    check();
    const id = setInterval(check, 10000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="text-sm">
      <span className="mr-3 font-semibold">ULTRA-Z</span>
      <span className={online ? 'text-sky-400' : 'text-rose-400'}>{online ? 'Backend Connected' : 'Backend Offline'}</span>
    </div>
  );
}
