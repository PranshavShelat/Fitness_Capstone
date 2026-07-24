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
    <div className={`bg-gray-900/60 backdrop-blur-md border border-gray-700/50 rounded-2xl p-6 ${className}`}>
      {children}
    </div>
  );
}

function ComingSoonBadge() {
  return (
    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500 bg-gray-800/80 px-2 py-1 rounded-full">
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
      { timeout: 10000 }
    );
  }, []);

  return (
    <GlassCard>
      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Weather</h3>
      {weather.status === 'loading' && <p className="text-gray-500 text-sm italic">Loading...</p>}
      {weather.status === 'error' && <p className="text-gray-500 text-sm">{weather.message}</p>}
      {weather.status === 'ready' && (
        <div className="flex items-center gap-3">
          <span className="text-4xl">{weather.emoji}</span>
          <div>
            <p className="text-2xl font-bold">{weather.temp}°C</p>
            <p className="text-sm text-gray-400">{weather.label}</p>
          </div>
        </div>
      )}
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
    <GlassCard className="md:col-span-2 lg:col-span-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Past Injury Reports</h3>
        <button
          onClick={loadReports}
          aria-label="Refresh reports"
          className="text-gray-500 hover:text-gray-300 text-xs"
        >
          ↻ Refresh
        </button>
      </div>

      {status === 'loading' && <p className="text-gray-500 text-sm italic">Loading...</p>}
      {status === 'error' && (
        <p className="text-gray-500 text-sm">Couldn't reach the AI Engine to load reports.</p>
      )}
      {status === 'ready' && reports.length === 0 && (
        <p className="text-gray-500 text-sm">No reports generated yet - they'll show up here after a workout.</p>
      )}
      {status === 'ready' && reports.length > 0 && (
        <div className="space-y-2">
          {reports.map(report => (
            <div key={report.filename} className="flex items-center justify-between text-sm bg-gray-800/40 rounded-lg px-4 py-2">
              <span className="text-gray-300">
                {new Date(report.created_at * 1000).toLocaleString()}
              </span>
              <button
                onClick={() => downloadReport(report.filename)}
                className="text-cyan-400 hover:text-cyan-300 font-semibold"
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
    <div className="min-h-screen bg-gray-950 text-white font-sans p-6 md:p-10">
      <div className="max-w-5xl mx-auto">

        {/* Welcome header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">
            {getGreeting()}
          </h1>
          <p className="text-gray-400 mt-1">Ready to train?</p>
        </div>

        {/* Start Workout CTA */}
        <button
          onClick={onStartWorkout}
          className="w-full mb-6 rounded-2xl p-8 text-left bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 transition-colors shadow-2xl"
        >
          <h2 className="text-2xl font-bold">Start Workout</h2>
          <p className="text-cyan-100 mt-1">Track squats, pushups, planks and more with real-time AI form coaching</p>
        </button>

        {/* Widget grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <WeatherCard />

          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Today's Workout</h3>
              <ComingSoonBadge />
            </div>
            <p className="text-gray-500 text-sm">Your personalized workout plan will appear here.</p>
          </GlassCard>

          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Meal Prep</h3>
              <ComingSoonBadge />
            </div>
            <p className="text-gray-500 text-sm">AI-generated meal suggestions will appear here.</p>
          </GlassCard>

          <GlassCard className="md:col-span-2 lg:col-span-3">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">AI Coach Chat</h3>
              <ComingSoonBadge />
            </div>
            <input
              type="text"
              disabled
              placeholder="Ask your AI coach... (coming soon)"
              className="w-full bg-gray-800/50 border border-gray-700 rounded-xl px-4 py-3 text-gray-500 placeholder-gray-600 cursor-not-allowed"
            />
          </GlassCard>

          <PastReportsCard />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
