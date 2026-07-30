import React, { useEffect, useState } from 'react';

const WEATHER_CODES = {
  0: { emoji: '☀️', label: 'Clear Sky' },
  1: { emoji: '🌤️', label: 'Mainly Clear' },
  2: { emoji: '⛅', label: 'Partly Cloudy' },
  3: { emoji: '☁️', label: 'Overcast' },
  45: { emoji: '🌫️', label: 'Fog' },
  48: { emoji: '🌫️', label: 'Fog' },
  51: { emoji: '🌦️', label: 'Light Drizzle' },
  53: { emoji: '🌦️', label: 'Drizzle' },
  55: { emoji: '🌦️', label: 'Dense Drizzle' },
  61: { emoji: '🌧️', label: 'Light Rain' },
  63: { emoji: '🌧️', label: 'Rain' },
  65: { emoji: '🌧️', label: 'Heavy Rain' },
  71: { emoji: '🌨️', label: 'Light Snow' },
  73: { emoji: '🌨️', label: 'Snow' },
  75: { emoji: '🌨️', label: 'Heavy Snow' },
  80: { emoji: '🌧️', label: 'Rain Showers' },
  81: { emoji: '🌧️', label: 'Rain Showers' },
  82: { emoji: '🌧️', label: 'Violent Showers' },
  95: { emoji: '⛈️', label: 'Thunderstorm' },
  96: { emoji: '⛈️', label: 'Thunderstorm' },
  99: { emoji: '⛈️', label: 'Thunderstorm' },
};

function describeWeatherCode(code) {
  return WEATHER_CODES[code] || { emoji: '🌡️', label: 'Weather' };
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function GlassCard({ children, className = '' }) {
  return (
    <div className={`bg-white/[0.04] backdrop-blur-2xl border border-white/10 rounded-[28px] p-6 ${className}`}>
      {children}
    </div>
  );
}

function ComingSoonBadge() {
  return (
    <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-neutral-500 bg-white/5 border border-white/10 px-2.5 py-1 rounded-full">
      Coming Soon
    </span>
  );
}

function WeatherCard() {
  const [weather, setWeather] = useState({ status: 'loading' });

  useEffect(() => {
    if (!navigator.geolocation) {
      setWeather({ status: 'error', message: 'Location not supported' });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { latitude, longitude } = position.coords;
          const res = await fetch(
            `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current_weather=true`
          );
          if (!res.ok) throw new Error('Weather request failed');
          const data = await res.json();
          const { emoji, label } = describeWeatherCode(data.current_weather.weathercode);
          setWeather({
            status: 'ready',
            temp: Math.round(data.current_weather.temperature),
            emoji,
            label,
          });
        } catch {
          setWeather({ status: 'error', message: 'Couldn\'t load weather' });
        }
      },
      (err) => {
        // err.code: 1 = permission denied, 2 = position unavailable, 3 = timeout.
        // Code 1 firing with no visible browser prompt usually means the OS itself
        // blocked it (e.g. macOS System Settings > Privacy & Security > Location
        // Services is off, or this browser isn't authorized there).
        const message = err.code === 1
          ? 'Location blocked (check OS location settings)'
          : err.code === 3
            ? 'Location request timed out'
            : 'Location unavailable';
        setWeather({ status: 'error', message });
      },
      { timeout: 30000, maximumAge: 5 * 60 * 1000 }
    );
  }, []);

  return (
    <GlassCard>
      <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-3">Weather</h3>
      {weather.status === 'loading' && <p className="text-neutral-500 text-sm italic">Loading...</p>}
      {weather.status === 'error' && <p className="text-neutral-500 text-sm">{weather.message}</p>}
      {weather.status === 'ready' && (
        <div className="flex items-center gap-3">
          <span className="text-4xl">{weather.emoji}</span>
          <div>
            <p className="text-2xl font-semibold tracking-tight">{weather.temp}°C</p>
            <p className="text-sm text-neutral-400">{weather.label}</p>
          </div>
        </div>
      )}
    </GlassCard>
  );
}

function ChatCard() {
  return (
    <GlassCard className="flex flex-col flex-1 min-h-[16rem]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em]">AI Coach Chat</h3>
        <ComingSoonBadge />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col justify-end gap-3 mb-4">
        <div className="flex items-end gap-2">
          <div className="w-7 h-7 shrink-0 rounded-full bg-white/10 flex items-center justify-center text-sm">✦</div>
          <div className="bg-white/[0.06] border border-white/10 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm text-neutral-300 max-w-[85%]">
            Hey! Once I'm live, ask me about your form, recovery, or what to train next.
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <input
          type="text"
          disabled
          placeholder="Ask your AI coach..."
          className="flex-1 bg-white/[0.03] border border-white/10 rounded-full px-4 py-2.5 text-sm text-neutral-500 placeholder-neutral-600 cursor-not-allowed"
        />
        <button
          disabled
          aria-label="Send message"
          className="w-9 h-9 shrink-0 rounded-full bg-white/10 text-neutral-500 flex items-center justify-center cursor-not-allowed"
        >
          ↑
        </button>
      </div>
    </GlassCard>
  );
}

async function downloadReport(filename) {
  const res = await fetch(`http://localhost:8000/reports/${encodeURIComponent(filename)}`);
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function PastReportsCard() {
  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
  const [reports, setReports] = useState([]);

  const loadReports = () => {
    setStatus('loading');
    fetch('http://localhost:8000/reports')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load reports');
        return res.json();
      })
      .then(data => {
        setReports(data);
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  };

  useEffect(() => {
    loadReports();
  }, []);

  return (
    <GlassCard>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em]">Past Injury Reports</h3>
        <button
          onClick={loadReports}
          aria-label="Refresh reports"
          className="text-neutral-500 hover:text-white text-xs transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {status === 'loading' && <p className="text-neutral-500 text-sm italic">Loading...</p>}
      {status === 'error' && (
        <p className="text-neutral-500 text-sm">Couldn't reach the AI Engine to load reports.</p>
      )}
      {status === 'ready' && reports.length === 0 && (
        <p className="text-neutral-500 text-sm">No reports generated yet - they'll show up here after a workout.</p>
      )}
      {status === 'ready' && reports.length > 0 && (
        <div className="space-y-2 max-h-80 overflow-y-auto pr-1 -mr-1">
          {reports.map(report => (
            <div key={report.filename} className="flex items-center justify-between text-sm bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3">
              <span className="text-neutral-300">
                {new Date(report.created_at * 1000).toLocaleString()}
              </span>
              <button
                onClick={() => downloadReport(report.filename)}
                className="text-white font-semibold hover:opacity-70 transition-opacity"
              >
                Download
              </button>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  );
}

function Dashboard({ onStartWorkout }) {
  return (
    <div className="min-h-screen bg-black text-white font-sans p-6 md:p-10 relative overflow-hidden">
      {/* Ambient glow, purely decorative */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full bg-white/[0.05] blur-[120px]" />

      <div className="max-w-6xl mx-auto relative">

        {/* Welcome header */}
        <div className="mb-8">
          <h1 className="text-4xl font-semibold tracking-tight">
            {getGreeting()}
          </h1>
          <p className="text-neutral-500 mt-1.5">Ready to train?</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:items-stretch">

          {/* Main column */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            {/* Start Workout CTA */}
            <button
              onClick={onStartWorkout}
              className="group w-full rounded-[28px] p-8 text-left bg-white text-black hover:bg-neutral-200 transition-colors duration-300 shadow-[0_0_60px_-15px_rgba(255,255,255,0.25)]"
            >
              <h2 className="text-2xl font-semibold tracking-tight">
                Start Workout <span className="inline-block transition-transform group-hover:translate-x-1">→</span>
              </h2>
              <p className="text-neutral-600 mt-1">Track squats, pushups, planks and more with real-time AI form coaching</p>
            </button>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <GlassCard>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em]">Today's Workout</h3>
                  <ComingSoonBadge />
                </div>
                <p className="text-neutral-500 text-sm">Your personalized workout plan will appear here.</p>
              </GlassCard>

              <GlassCard>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em]">Meal Prep</h3>
                  <ComingSoonBadge />
                </div>
                <p className="text-neutral-500 text-sm">AI-generated meal suggestions will appear here.</p>
              </GlassCard>
            </div>

            <PastReportsCard />
          </div>

          {/* Side column - stretches to match the main column's height (lg:items-stretch
              above), so the chat card can fill the leftover space below Weather and end
              up flush with the bottom of the main column instead of a fixed/arbitrary size. */}
          <div className="flex flex-col gap-6 lg:h-full lg:sticky lg:top-10">
            <WeatherCard />
            <ChatCard />
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
