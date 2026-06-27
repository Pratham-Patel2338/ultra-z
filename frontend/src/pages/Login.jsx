import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!pin) {
      setError('PIN is required');
      return;
    }
    setLoading(true);
    try {
      const ok = await login(pin);
      if (ok) {
        navigate('/dashboard');
      } else {
        setError('Invalid PIN');
      }
    } catch (err) {
      setError('Unable to connect to ULTRA-Z backend');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050816] flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
        className="w-full max-w-md p-8 rounded-2xl bg-white/5 border border-white/8 shadow-neon backdrop-blur-md"
      >
        <div className="text-center mb-6">
          <div className="mx-auto mb-4 w-20 h-20 rounded-full bg-gradient-to-br from-sky-400 to-indigo-600 flex items-center justify-center shadow-glow">
            <span className="text-2xl font-bold text-white">UZ</span>
          </div>
          <h1 className="text-xl font-semibold text-white">ULTRA-Z Authentication</h1>
          <p className="text-sm text-slate-300 mt-2">Enter your PIN to access the assistant dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-300 mb-2">PIN</label>
            <input
              type="password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              className="w-full bg-black/30 border border-white/10 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-sky-400"
              placeholder="Enter PIN"
            />
          </div>

          {error && <div className="text-sm text-rose-400">{error}</div>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-500 text-white font-semibold shadow-lg hover:opacity-95 disabled:opacity-60"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="mt-6 text-xs text-slate-400 text-center">Demo PIN: use the backend admin PIN configured in .env</div>
      </motion.div>

      <div className="fixed inset-0 -z-10 animate-pulse" style={{ background: 'radial-gradient(circle at 10% 20%, rgba(14,165,233,0.06), transparent 10%), radial-gradient(circle at 90% 80%, rgba(99,102,241,0.04), transparent 10%)' }} />
    </div>
  );
}
