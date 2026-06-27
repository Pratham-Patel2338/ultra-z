export default function SettingsPanel({ settings, onUpdateSettings, onRefresh }) {
  const handleChange = (field, value) => {
    onUpdateSettings({ ...settings, [field]: value });
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="glass-panel rounded-[28px] p-5">
          <h3 className="mb-4 text-lg font-semibold text-white">Model</h3>
          <select
            value={settings.model}
            onChange={(e) => handleChange('model', e.target.value)}
            className="glass-input w-full"
          >
            <option value="ollama-ultra-3">ollama-ultra-3</option>
            <option value="ollama-mini">ollama-mini</option>
            <option value="gpt-4o">gpt-4o</option>
          </select>
        </div>

        <div className="glass-panel rounded-[28px] p-5">
          <h3 className="mb-4 text-lg font-semibold text-white">Voice</h3>
          <select
            value={settings.voice}
            onChange={(e) => handleChange('voice', e.target.value)}
            className="glass-input w-full"
          >
            <option>English</option>
            <option>Hindi</option>
            <option>Gujarati</option>
            <option>Jarvis</option>
          </select>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="glass-panel rounded-[28px] p-5">
          <h3 className="mb-4 text-lg font-semibold text-white">Wakeword</h3>
          <label className="flex items-center gap-3 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={settings.wakewordEnabled}
              onChange={(e) => handleChange('wakewordEnabled', e.target.checked)}
            />
            Enable wakeword detection
          </label>
        </div>

        <div className="glass-panel rounded-[28px] p-5">
          <h3 className="mb-4 text-lg font-semibold text-white">Theme</h3>
          <select
            value={settings.theme}
            onChange={(e) => handleChange('theme', e.target.value)}
            className="glass-input w-full"
          >
            <option>Dark</option>
            <option>Light</option>
            <option>System</option>
          </select>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="glass-panel rounded-[28px] p-5">
          <h3 className="mb-4 text-lg font-semibold text-white">Volume</h3>
          <input
            type="range"
            min="0"
            max="100"
            value={settings.volume}
            onChange={(e) => handleChange('volume', Number(e.target.value))}
            className="w-full"
          />
          <div className="mt-3 text-sm text-slate-300">{settings.volume}%</div>
        </div>

        <div className="glass-panel rounded-[28px] p-5">
          <h3 className="mb-4 text-lg font-semibold text-white">Temperature</h3>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={settings.temperature}
            onChange={(e) => handleChange('temperature', Number(e.target.value))}
            className="w-full"
          />
          <div className="mt-3 text-sm text-slate-300">{settings.temperature}</div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 rounded-[28px] border border-white/10 bg-slate-950/70 p-5">
        <div>
          <p className="text-sm text-slate-300">Sync remote settings</p>
          <p className="text-xs text-slate-500">Changes are saved locally and sent to the backend.</p>
        </div>
        <button type="button" onClick={onRefresh} className="btn primary-btn">Refresh</button>
      </div>
    </div>
  );
}
