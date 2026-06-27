import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-[#050816] flex items-center justify-center p-6">
      <motion.div initial={{ scale: 0.98 }} animate={{ scale: 1 }} className="w-full max-w-3xl p-8 rounded-2xl bg-white/5 border border-white/8 shadow-neon backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold text-white">ULTRA-Z</h2>
            <p className="text-slate-300 mt-2">Authentication successful — You are logged in.</p>
          </div>
          <div>
            <button onClick={handleLogout} className="px-4 py-2 rounded-lg bg-rose-500 text-white">Logout</button>
          </div>
        </div>

        <div className="mt-8 text-slate-300">
          <p>This dashboard is a placeholder. The main assistant UI will appear here.</p>
        </div>
      </motion.div>
    </div>
  );
}
