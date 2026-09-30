import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
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

// US EPA AQI breakpoints (0-500 scale).
function describeAqi(aqi) {
  if (aqi <= 50) return { label: 'Good', color: 'text-emerald-400' };
  if (aqi <= 100) return { label: 'Moderate', color: 'text-yellow-400' };
  if (aqi <= 150) return { label: 'Unhealthy (Sensitive)', color: 'text-orange-400' };
  if (aqi <= 200) return { label: 'Unhealthy', color: 'text-red-400' };
  if (aqi <= 300) return { label: 'Very Unhealthy', color: 'text-purple-400' };
  return { label: 'Hazardous', color: 'text-red-700' };
}

// Standard UV index scale.
function describeUv(uv) {
  if (uv <= 2) return { label: 'Low', color: 'text-emerald-400' };
  if (uv <= 5) return { label: 'Moderate', color: 'text-yellow-400' };
  if (uv <= 7) return { label: 'High', color: 'text-orange-400' };
  if (uv <= 10) return { label: 'Very High', color: 'text-red-400' };
  return { label: 'Extreme', color: 'text-purple-400' };
}

const WEATHER_STAT_LABEL_CLASS = 'text-[10px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-1.5';
const WEATHER_STAT_VALUE_CLASS = 'text-xl font-semibold tracking-tight';

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

function WeatherCard() {
  const [weather, setWeather] = useState({ status: 'loading' });

  useEffect(() => {
    if (!navigator.geolocation) {
      setWeather({ status: 'error', message: 'Location not supported' });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        try {
          const res = await fetch(
            `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}` +
            `&current=weather_code,temperature_2m,relative_humidity_2m,wind_speed_10m,uv_index`
          );
          if (!res.ok) throw new Error('Weather request failed');
          const data = await res.json();
          const current = data.current;
          const { emoji, label } = describeWeatherCode(current.weather_code);

          // AQI is a bonus alongside the core weather reading - if this call fails,
          // still show the weather rather than losing the whole card over it.
          let aqi = null;
          try {
            const aqiRes = await fetch(
              `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${latitude}&longitude=${longitude}&current=us_aqi`
            );
            if (aqiRes.ok) {
              const aqiData = await aqiRes.json();
              const value = aqiData.current?.us_aqi;
              if (typeof value === 'number') aqi = Math.round(value);
            }
          } catch {
            // swallow - aqi stays null
          }

          setWeather({
            status: 'ready',
            temp: Math.round(current.temperature_2m),
            emoji,
            label,
            aqi,
            humidity: Math.round(current.relative_humidity_2m),
            windSpeed: Math.round(current.wind_speed_10m),
            uvIndex: current.uv_index,
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
        <>
          <div className="flex items-center gap-3">
            <span className="text-4xl">{weather.emoji}</span>
            <div>
              <p className="text-2xl font-semibold tracking-tight">{weather.temp}°C</p>
              <p className="text-sm text-neutral-400">{weather.label}</p>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4 mt-5 pt-4 border-t border-white/10">
            {weather.aqi != null && (
              <div>
                <p className={WEATHER_STAT_LABEL_CLASS}>AQI</p>
                <p className={`${WEATHER_STAT_VALUE_CLASS} ${describeAqi(weather.aqi).color}`}>{weather.aqi}</p>
                <p className="text-xs text-neutral-500 mt-0.5">{describeAqi(weather.aqi).label}</p>
              </div>
            )}

            <div>
              <p className={WEATHER_STAT_LABEL_CLASS}>Humidity</p>
              <p className={WEATHER_STAT_VALUE_CLASS}>{weather.humidity}%</p>
            </div>

            <div>
              <p className={WEATHER_STAT_LABEL_CLASS}>Wind</p>
              <p className={WEATHER_STAT_VALUE_CLASS}>
                {weather.windSpeed} <span className="text-sm font-normal text-neutral-400">km/h</span>
              </p>
            </div>

            {weather.uvIndex != null && (
              <div>
                <p className={WEATHER_STAT_LABEL_CLASS}>UV Index</p>
                <p className={`${WEATHER_STAT_VALUE_CLASS} ${describeUv(weather.uvIndex).color}`}>{Math.round(weather.uvIndex)}</p>
                <p className="text-xs text-neutral-500 mt-0.5">{describeUv(weather.uvIndex).label}</p>
              </div>
            )}
          </div>
        </>
      )}
    </GlassCard>
  );
}

const PROFILE_STORAGE_KEY = 'fitness_profile';

const GOALS = [
  { id: 'CUT', label: 'Cut' },
  { id: 'MAINTAIN', label: 'Maintain' },
  { id: 'BULK', label: 'Bulk' },
];

const DIETS = [
  { id: 'VEG', label: 'Vegetarian' },
  { id: 'NON_VEG', label: 'Non-Vegetarian' },
];

// The exact 3-way split the meal-plan RAG pipeline retrieves against - a strict
// constraint, so this is always fully resolved (never left ambiguous) before a
// profile can be saved.
function dietCategory(profile) {
  if (profile.diet === 'NON_VEG') return 'NON_VEG';
  return profile.eatsEggs ? 'VEG_EGGS' : 'VEG_NO_EGGS';
}

function dietLabel(profile) {
  if (profile.diet === 'NON_VEG') return 'Non-Vegetarian';
  return profile.eatsEggs ? 'Vegetarian (eats eggs)' : 'Vegetarian (no eggs)';
}

function bmiCategory(bmi) {
  if (bmi < 18.5) return 'Underweight';
  if (bmi < 25) return 'Normal';
  if (bmi < 30) return 'Overweight';
  return 'Obese';
}

function loadProfile() {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const PROFILE_HISTORY_KEY = 'fitness_profile_history';

function loadProfileHistory() {
  try {
    const raw = localStorage.getItem(PROFILE_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    // Backfills ids for entries saved before per-entry delete existed - without this,
    // those entries would all share the same (missing) id and deleting one would
    // delete all of them at once.
    const migrated = parsed.map(entry => (entry.id ? entry : { ...entry, id: crypto.randomUUID() }));
    if (migrated.some((entry, i) => entry !== parsed[i])) {
      localStorage.setItem(PROFILE_HISTORY_KEY, JSON.stringify(migrated));
    }
    return migrated;
  } catch {
    return [];
  }
}

// Shared across both the Today's Workout and Meal Prep cards - a goal/BMI
// entered in either place immediately shows up summarized in both, since
// the plan generation both cards will eventually drive is conditioned on
// this same profile.
//
// Two distinct ways to change the profile:
// - updateProfile: plain in-place correction (e.g. fixing a typo) - the old
//   values are simply replaced, nothing is kept.
// - recordNewStats: a new weigh-in - the CURRENT values are archived into
//   history first, then the new values become the profile, so progress over
//   time stays visible instead of being silently overwritten.
function useFitnessProfile() {
  const [profile, setProfile] = useState(loadProfile);
  const [history, setHistory] = useState(loadProfileHistory);

  const updateProfile = (next) => {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(next));
    setProfile(next);
  };

  const clearProfile = () => {
    localStorage.removeItem(PROFILE_STORAGE_KEY);
    setProfile(null);
  };

  const recordNewStats = (next) => {
    if (profile) {
      const entry = { id: crypto.randomUUID(), heightCm: profile.heightCm, weightKg: profile.weightKg, recordedAt: Date.now() };
      const nextHistory = [entry, ...history];
      localStorage.setItem(PROFILE_HISTORY_KEY, JSON.stringify(nextHistory));
      setHistory(nextHistory);
    }
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(next));
    setProfile(next);
  };

  const deleteHistoryEntry = (id) => {
    const nextHistory = history.filter(entry => entry.id !== id);
    localStorage.setItem(PROFILE_HISTORY_KEY, JSON.stringify(nextHistory));
    setHistory(nextHistory);
  };

  const clearHistory = () => {
    localStorage.removeItem(PROFILE_HISTORY_KEY);
    setHistory([]);
  };

  return { profile, updateProfile, clearProfile, recordNewStats, history, deleteHistoryEntry, clearHistory };
}

const SEXES = [
  { id: 'MALE', label: 'Male' },
  { id: 'FEMALE', label: 'Female' },
];

function FitnessProfileForm({ initial, onSave, onCancel }) {
  const [heightCm, setHeightCm] = useState(initial?.heightCm ?? '');
  const [weightKg, setWeightKg] = useState(initial?.weightKg ?? '');
  const [age, setAge] = useState(initial?.age ?? '');
  const [sex, setSex] = useState(initial?.sex ?? null);
  const [goal, setGoal] = useState(initial?.goal ?? 'MAINTAIN');
  const [diet, setDiet] = useState(initial?.diet ?? null);
  const [eatsEggs, setEatsEggs] = useState(initial?.eatsEggs ?? null);

  const dietResolved = diet === 'NON_VEG' || (diet === 'VEG' && eatsEggs !== null);
  const canSave = Number(heightCm) > 0 && Number(weightKg) > 0 && Number(age) > 0 && sex && dietResolved;

  return (
    <div className="space-y-3 mb-4">
      <div className="grid grid-cols-3 gap-3">
        <label className="block">
          <span className="text-xs text-neutral-500">Height (cm)</span>
          <input
            type="number"
            value={heightCm}
            onChange={e => setHeightCm(e.target.value)}
            placeholder="175"
            className="mt-1 w-full bg-white/[0.05] border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-neutral-600 focus:outline-none focus:border-white/30"
          />
        </label>
        <label className="block">
          <span className="text-xs text-neutral-500">Weight (kg)</span>
          <input
            type="number"
            value={weightKg}
            onChange={e => setWeightKg(e.target.value)}
            placeholder="70"
            className="mt-1 w-full bg-white/[0.05] border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-neutral-600 focus:outline-none focus:border-white/30"
          />
        </label>
        <label className="block">
          <span className="text-xs text-neutral-500">Age</span>
          <input
            type="number"
            value={age}
            onChange={e => setAge(e.target.value)}
            placeholder="28"
            className="mt-1 w-full bg-white/[0.05] border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-neutral-600 focus:outline-none focus:border-white/30"
          />
        </label>
      </div>

      <div>
        <span className="text-xs text-neutral-500 mb-1.5 block">Sex</span>
        <div className="flex gap-2">
          {SEXES.map(s => (
            <button
              key={s.id}
              onClick={() => setSex(s.id)}
              className={`flex-1 text-xs font-medium py-2 rounded-full border transition-colors ${
                sex === s.id
                  ? 'bg-white text-black border-white'
                  : 'bg-white/[0.03] border-white/10 text-neutral-300 hover:bg-white/[0.07]'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <span className="text-xs text-neutral-500 mb-1.5 block">Goal</span>
        <div className="flex gap-2">
          {GOALS.map(g => (
            <button
              key={g.id}
              onClick={() => setGoal(g.id)}
              className={`flex-1 text-xs font-medium py-2 rounded-full border transition-colors ${
                goal === g.id
                  ? 'bg-white text-black border-white'
                  : 'bg-white/[0.03] border-white/10 text-neutral-300 hover:bg-white/[0.07]'
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <span className="text-xs text-neutral-500 mb-1.5 block">Diet</span>
        <div className="flex gap-2">
          {DIETS.map(d => (
            <button
              key={d.id}
              onClick={() => { setDiet(d.id); if (d.id === 'NON_VEG') setEatsEggs(null); }}
              className={`flex-1 text-xs font-medium py-2 rounded-full border transition-colors ${
                diet === d.id
                  ? 'bg-white text-black border-white'
                  : 'bg-white/[0.03] border-white/10 text-neutral-300 hover:bg-white/[0.07]'
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>

      {diet === 'VEG' && (
        <div>
          <span className="text-xs text-neutral-500 mb-1.5 block">Do you eat eggs?</span>
          <div className="flex gap-2">
            {[{ id: true, label: 'Yes' }, { id: false, label: 'No' }].map(opt => (
              <button
                key={String(opt.id)}
                onClick={() => setEatsEggs(opt.id)}
                className={`flex-1 text-xs font-medium py-2 rounded-full border transition-colors ${
                  eatsEggs === opt.id
                    ? 'bg-white text-black border-white'
                    : 'bg-white/[0.03] border-white/10 text-neutral-300 hover:bg-white/[0.07]'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          disabled={!canSave}
          onClick={() => onSave({
            heightCm: Number(heightCm), weightKg: Number(weightKg), age: Number(age), sex, goal, diet,
            eatsEggs: diet === 'VEG' ? eatsEggs : null,
          })}
          className="flex-1 py-2 rounded-full text-sm font-semibold bg-white text-black hover:bg-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Save
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            className="py-2 px-4 rounded-full text-sm font-medium text-neutral-400 hover:text-neutral-200 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

function TimelineModal({ profile, history, onClose, onDeleteEntry, onClearAll }) {
  const [confirmingClear, setConfirmingClear] = useState(false);
  const heightM = profile.heightCm / 100;
  const currentBmi = profile.weightKg / (heightM * heightM);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-neutral-950 border border-white/10 rounded-[28px] p-6 max-h-[80vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4 shrink-0">
          <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em]">Height &amp; Weight Timeline</h3>
          <button onClick={onClose} aria-label="Close" className="text-neutral-500 hover:text-white text-lg leading-none transition-colors">
            &times;
          </button>
        </div>

        <div className="space-y-2 overflow-y-auto pr-1 -mr-1 flex-1 min-h-0">
          <div className="flex items-center justify-between text-sm bg-white/[0.07] border border-white/10 rounded-2xl px-4 py-3">
            <div>
              <p className="text-white font-medium">Current</p>
              <p className="text-neutral-400 text-xs mt-0.5">
                {profile.heightCm}cm &middot; {profile.weightKg}kg &middot; BMI {currentBmi.toFixed(1)}
              </p>
            </div>
          </div>

          {history.map(entry => {
            const entryHeightM = entry.heightCm / 100;
            const entryBmi = entry.weightKg / (entryHeightM * entryHeightM);
            return (
              <div
                key={entry.id}
                className="flex items-center justify-between text-sm bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3"
              >
                <div>
                  <p className="text-neutral-300">{new Date(entry.recordedAt).toLocaleString()}</p>
                  <p className="text-neutral-500 text-xs mt-0.5">
                    {entry.heightCm}cm &middot; {entry.weightKg}kg &middot; BMI {entryBmi.toFixed(1)}
                  </p>
                </div>
                <button
                  onClick={() => onDeleteEntry(entry.id)}
                  className="text-xs text-neutral-500 hover:text-white transition-colors shrink-0"
                >
                  Delete
                </button>
              </div>
            );
          })}
        </div>

        {history.length === 0 ? (
          <p className="text-neutral-500 text-sm mt-3 shrink-0">No past entries yet - use "Record New Stats" to add to the timeline.</p>
        ) : (
          <div className="pt-4 mt-4 border-t border-white/10 shrink-0">
            {confirmingClear ? (
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">Delete all {history.length} past entries?</span>
                <div className="flex gap-3">
                  <button
                    onClick={() => setConfirmingClear(false)}
                    className="text-xs text-neutral-500 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => { onClearAll(); setConfirmingClear(false); }}
                    className="text-xs text-red-400 hover:text-red-300 transition-colors"
                  >
                    Confirm Clear All
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setConfirmingClear(true)}
                className="text-xs text-neutral-500 hover:text-white transition-colors"
              >
                Clear All
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const BMI_CATEGORY_COLORS = {
  Underweight: 'text-amber-300',
  Normal: 'text-emerald-400',
  Overweight: 'text-amber-300',
  Obese: 'text-red-400',
};
const PROFILE_ACTION_CLASS =
  'text-xs font-medium text-neutral-400 border border-white/10 rounded-full px-3 py-1.5 hover:text-white hover:border-white/30 transition-colors';

function FitnessProfileSummary({ profile, onEdit, onRecordNew, onClearProfile, history, onDeleteHistoryEntry, onClearHistory }) {
  const [showTimeline, setShowTimeline] = useState(false);
  const [confirmingClearProfile, setConfirmingClearProfile] = useState(false);
  const heightM = profile.heightCm / 100;
  const bmi = profile.weightKg / (heightM * heightM);
  const goalLabel = GOALS.find(g => g.id === profile.goal)?.label ?? profile.goal;
  const sexLabel = SEXES.find(s => s.id === profile.sex)?.label ?? profile.sex;

  return (
    <div>
      {/* Stats as tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {[
          { label: 'BMI', value: bmi.toFixed(1), sub: bmiCategory(bmi), subClass: BMI_CATEGORY_COLORS[bmiCategory(bmi)] },
          { label: 'Height', value: profile.heightCm, sub: 'cm' },
          { label: 'Weight', value: profile.weightKg, sub: 'kg' },
          { label: 'Goal', value: goalLabel, sub: `${profile.age} yrs \u00b7 ${sexLabel}` },
          { label: 'Diet', value: dietLabel(profile).split(' (')[0], sub: (dietLabel(profile).match(/\((.*)\)/) || [])[1] || '' },
        ].map(tile => (
          <div key={tile.label} className="bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3 min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-neutral-500">{tile.label}</p>
            <p className="text-lg font-semibold tracking-tight text-white mt-0.5 truncate">{tile.value}</p>
            <p className={`text-xs truncate ${tile.subClass || 'text-neutral-500'}`}>{tile.sub || '\u00a0'}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center justify-end gap-2 mt-3">
        {confirmingClearProfile ? (
          <>
            <span className="text-xs text-neutral-500 mr-1">Clear your profile?</span>
            <button onClick={() => setConfirmingClearProfile(false)} className={PROFILE_ACTION_CLASS}>Cancel</button>
            <button
              onClick={() => { onClearProfile(); setConfirmingClearProfile(false); }}
              className="text-xs font-medium text-red-300 border border-red-400/30 rounded-full px-3 py-1.5 hover:bg-red-500/10 transition-colors"
            >
              Confirm Clear
            </button>
          </>
        ) : (
          <>
            <button onClick={() => setShowTimeline(true)} className={PROFILE_ACTION_CLASS}>View Timeline</button>
            <button onClick={onRecordNew} className={PROFILE_ACTION_CLASS}>Record New Stats</button>
            <button onClick={onEdit} className={PROFILE_ACTION_CLASS}>Edit</button>
            <button onClick={() => setConfirmingClearProfile(true)} className={PROFILE_ACTION_CLASS}>Clear</button>
          </>
        )}
      </div>

      {showTimeline && (
        <TimelineModal
          profile={profile}
          history={history}
          onClose={() => setShowTimeline(false)}
          onDeleteEntry={onDeleteHistoryEntry}
          onClearAll={onClearHistory}
        />
      )}
    </div>
  );
}

// Drop-in for either card: shows the input form until a profile is saved, then
// a compact BMI/goal/diet summary with Edit and Record New Stats affordances
// plus a collapsible height/weight history. mode/setMode are lifted to
// Dashboard and shared by both cards - previously each card had its own
// independent editing state, so saving the profile from one card left the
// other stuck showing a stale, already-saved form.
//
// mode is null (not editing), 'edit' (in-place correction, no history entry),
// or 'record' (a new weigh-in - the current values get archived first).
function FitnessProfileGate({ profile, updateProfile, clearProfile, recordNewStats, mode, setMode, history, deleteHistoryEntry, clearHistory }) {
  if (mode || !profile) {
    return (
      <FitnessProfileForm
        initial={profile}
        onSave={(next) => {
          if (mode === 'record') recordNewStats(next); else updateProfile(next);
          setMode(null);
        }}
        onCancel={profile ? () => setMode(null) : undefined}
      />
    );
  }
  return (
    <FitnessProfileSummary
      profile={profile}
      onEdit={() => setMode('edit')}
      onRecordNew={() => setMode('record')}
      onClearProfile={clearProfile}
      history={history}
      onDeleteHistoryEntry={deleteHistoryEntry}
      onClearHistory={clearHistory}
    />
  );
}

const WORKOUT_PLAN_STORAGE_KEY = 'fitness_workout_plan';
const MEAL_PLAN_STORAGE_KEY = 'fitness_meal_plan';
const WEEKDAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// Deliberately separate keys - the workout plan doesn't depend on diet at all, so a diet
// change alone shouldn't mark it stale (only the meal plan needs to react to that).
function workoutProfileKey(profile) {
  return profile ? `${profile.heightCm}-${profile.weightKg}-${profile.age}-${profile.sex}-${profile.goal}` : null;
}

function mealProfileKey(profile) {
  return profile
    ? `${profile.heightCm}-${profile.weightKg}-${profile.age}-${profile.sex}-${profile.goal}-${dietCategory(profile)}`
    : null;
}

function loadCachedPlan(storageKey) {
  try {
    const raw = localStorage.getItem(storageKey);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function todaysPlanDay(plan) {
  const todayName = WEEKDAY_NAMES[new Date().getDay()];
  return plan.days.find(d => d.day === todayName) ?? plan.days[0];
}

// One independent plan-fetching hook, parameterized per kind (workout/meal) - each gets
// its own cache key and its own endpoint, so regenerating one can never touch the other.
// They used to share a single combined plan/endpoint, which meant clicking "Regenerate"
// on either card silently regenerated both.
function usePlan(profile, { storageKey, endpoint, keyFn, buildParams }) {
  const key = keyFn(profile);
  const [state, setState] = useState(() => {
    const cached = loadCachedPlan(storageKey);
    return cached && cached.profileKey === key
      ? { status: 'ready', plan: cached.plan }
      : { status: 'idle', plan: null };
  });

  useEffect(() => {
    const cached = loadCachedPlan(storageKey);
    setState(
      cached && cached.profileKey === key
        ? { status: 'ready', plan: cached.plan }
        : { status: 'idle', plan: null }
    );
  }, [key]);

  const generate = async () => {
    if (!profile) return;
    setState({ status: 'loading', plan: null });
    try {
      const params = buildParams(profile);
      const res = await fetch(`http://localhost:8000${endpoint}?${params}`);
      if (!res.ok) throw new Error('Plan request failed');
      const plan = await res.json();
      localStorage.setItem(storageKey, JSON.stringify({ profileKey: key, plan }));
      setState({ status: 'ready', plan });
    } catch {
      setState({ status: 'error', plan: null });
    }
  };

  // A plan made by the coach chat replaces the card's plan exactly like the
  // Generate button would - saved, so it survives a page refresh.
  const replaceWith = (plan) => {
    if (!plan || !Array.isArray(plan.days)) return;
    localStorage.setItem(storageKey, JSON.stringify({ profileKey: key, plan }));
    setState({ status: 'ready', plan });
  };

  return { ...state, generate, replaceWith };
}

function useWorkoutPlan(profile) {
  return usePlan(profile, {
    storageKey: WORKOUT_PLAN_STORAGE_KEY,
    endpoint: '/plan/workout',
    keyFn: workoutProfileKey,
    buildParams: (p) => new URLSearchParams({
      height: p.heightCm, weight: p.weightKg, age: p.age, sex: p.sex, goal: p.goal,
    }),
  });
}

function useMealPlan(profile) {
  return usePlan(profile, {
    storageKey: MEAL_PLAN_STORAGE_KEY,
    endpoint: '/plan/meal',
    keyFn: mealProfileKey,
    buildParams: (p) => new URLSearchParams({
      height: p.heightCm, weight: p.weightKg, age: p.age, sex: p.sex, goal: p.goal, diet: dietCategory(p),
    }),
  });
}

function GeneratePlanButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full py-2.5 rounded-full text-sm font-semibold bg-white text-black hover:bg-neutral-200 transition-colors"
    >
      Generate My Plan
    </button>
  );
}

function SourcesFooter({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="pt-3 mt-3 border-t border-white/10">
      <p className="text-[10px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-1.5">Sources</p>
      <ul className="text-xs text-neutral-500 space-y-0.5">
        {sources.map((source, i) => <li key={i}>{source}</li>)}
      </ul>
    </div>
  );
}
// Pop-up shared by the Today's Workout and Meal Prep cards.
// renderDay(day) draws one day's content, so the same pop-up works for both.
// Pop-up shared by the Today's Workout and Meal Prep cards.
// Rendered with createPortal straight into <body>: the dashboard cards use a blur
// effect, and a blurred parent traps `position: fixed` inside itself - which is
// why the pop-up was stuck inside its card instead of covering the screen.
function PlanModal({ title, plan, renderDay, header, onClose }) {
  const today = todaysPlanDay(plan);
  const [view, setView] = useState('today'); // 'today' | 'week'
  const days = view === 'today' ? [today] : plan.days;

  // Close on Escape, and stop the page behind from scrolling while open
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  const tabClass = active =>
    `px-5 py-2 rounded-full text-sm font-semibold transition-colors ${
      active ? 'bg-white text-black' : 'text-neutral-400 hover:text-white'
    }`;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-xl p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl h-[90vh] bg-neutral-950/95 border border-white/10 rounded-[32px] p-6 sm:p-8 flex flex-col shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Title + close button */}
        <div className="flex items-center justify-between mb-5 shrink-0">
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-10 h-10 rounded-full bg-white/[0.06] hover:bg-white/15 text-neutral-300 hover:text-white text-xl leading-none transition-colors"
          >
            &times;
          </button>
        </div>

        {/* Today / Full week switch + optional header (e.g. calorie target) */}
        <div className="flex flex-wrap items-center gap-4 mb-5 shrink-0">
          <div className="flex gap-1 bg-white/[0.05] border border-white/10 rounded-full p-1">
            <button className={tabClass(view === 'today')} onClick={() => setView('today')}>Today</button>
            <button className={tabClass(view === 'week')} onClick={() => setView('week')}>Full week</button>
          </div>
          {header}
        </div>

        {/* Scrollable days: one column for today, a 2-column grid for the week */}
        <div
          className={`overflow-y-auto flex-1 min-h-0 pr-2 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.2)_transparent] ${
            view === 'week' ? 'grid grid-cols-1 md:grid-cols-2 gap-3 content-start' : 'space-y-3'
          }`}
        >
          {days.map(day => (
            <div
              key={day.day}
              className={`border rounded-2xl px-5 py-4 ${
                day.day === today.day ? 'bg-white/[0.08] border-white/20' : 'bg-white/[0.03] border-white/5'
              }`}
            >
              <p className="text-base font-semibold mb-2">
                {day.day}{day.day === today.day ? ' (Today)' : ''}
              </p>
              {renderDay(day)}
            </div>
          ))}
        </div>

        <div className="shrink-0">
          <SourcesFooter sources={plan.sources} />
        </div>
      </div>
    </div>,
    document.body
  );
}
// One day of the workout plan. compact = the short dashboard-card version.
function WorkoutDay({ day, compact = false }) {
  if (day.workout.is_rest) {
    return (
      <div>
        <span className="inline-block text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
          Rest day
        </span>
        {!compact && day.notes && (
          <p className="text-xs text-neutral-400 mt-3 pl-3 border-l-2 border-white/15">{day.notes}</p>
        )}
      </div>
    );
  }

  const exercises = day.workout.exercises;
  const shown = compact ? exercises.slice(0, 4) : exercises;
  return (
    <div>
      <ul className="divide-y divide-white/5">
        {shown.map((ex, i) => (
          <li key={i} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
            <span className="flex items-center gap-3 min-w-0">
              <span className="w-5 h-5 shrink-0 rounded-full bg-white/10 text-[10px] font-semibold text-neutral-300 flex items-center justify-center">
                {i + 1}
              </span>
              <span className="text-sm text-neutral-200 truncate">{ex.name}</span>
            </span>
            <span className="shrink-0 text-xs font-semibold tabular-nums text-white bg-white/10 rounded-full px-2.5 py-1">
              {ex.sets_reps.replace('x', ' \u00d7 ')}
            </span>
          </li>
        ))}
      </ul>
      {compact && exercises.length > shown.length && (
        <p className="text-xs text-neutral-500 mt-2">+{exercises.length - shown.length} more</p>
      )}
      {!compact && day.notes && (
        <p className="text-xs text-neutral-400 mt-3 pl-3 border-l-2 border-white/15">{day.notes}</p>
      )}
    </div>
  );
}

const MEALS = [
  { key: 'breakfast', label: 'Breakfast' },
  { key: 'lunch', label: 'Lunch' },
  { key: 'dinner', label: 'Dinner' },
  { key: 'snack', label: 'Snack' },
];

// "80g oats in 250ml milk, 32g peanut butter, and 1 banana" -> one ingredient per
// item. Splits on commas and on "and" before a quantity ("and 15g chia seeds"),
// but never on a comma inside brackets like "(3 large eggs, 1 yolk)".
function splitIngredients(text) {
  const parts = [];
  let depth = 0;
  let current = '';
  for (const ch of String(text || '')) {
    if (ch === '(') depth++;
    if (ch === ')') depth = Math.max(0, depth - 1);
    if (ch === ',' && depth === 0) {
      parts.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  parts.push(current);
  return parts
    .flatMap(part => part.split(/\s+and\s+(?=\d)/))
    .map(part => part.trim().replace(/^and\s+/i, '').replace(/\.$/, ''))
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1));
}

// One day of the meal plan. compact = one line per meal on the dashboard card;
// the pop-up lists every ingredient on its own line.
function MealDay({ day, compact = false }) {
  return (
    <ul className="divide-y divide-white/5">
      {MEALS.map(meal => (
        <li key={meal.key} className="py-2 first:pt-0 last:pb-0">
          <p className="text-sm font-semibold text-white">{meal.label}</p>
          {compact ? (
            <p className="text-sm text-neutral-400 leading-snug mt-0.5 line-clamp-1">{day.meals[meal.key]}</p>
          ) : (
            <ul className="mt-1 space-y-0.5">
              {splitIngredients(day.meals[meal.key]).map((item, i) => (
                <li key={i} className="flex gap-2 text-sm text-neutral-300 leading-snug">
                  <span className="mt-[0.55em] w-1 h-1 shrink-0 rounded-full bg-neutral-500" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

// Shown while a plan is missing, loading or failed - same for both cards.
function PlanStatus({ planState }) {
  if (planState.status === 'idle') return <GeneratePlanButton onClick={planState.generate} />;
  if (planState.status === 'loading') {
    return <p className="text-neutral-500 text-sm italic">Building your personalized plan with AI - this can take up to 30s...</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-neutral-500 text-sm">Couldn't generate a plan - is the AI Engine running?</p>
      <button onClick={planState.generate} className="text-xs text-white underline">Try again</button>
    </div>
  );
}

// Today's plan as a clickable box that opens the pop-up.
function TodayPreview({ day, onOpen, children }) {
  return (
    <button
      onClick={onOpen}
      className="w-full text-left bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3 hover:bg-white/[0.07] hover:border-white/15 transition-colors"
    >
      <p className="text-sm font-semibold mb-1.5">{day.day} (Today)</p>
      {children}
      <p className="text-xs text-neutral-500 mt-2">Click to view today or the full week &rarr;</p>
    </button>
  );
}

function WorkoutPlanContent({ planState }) {
  const [open, setOpen] = useState(false);
  if (planState.status !== 'ready') return <PlanStatus planState={planState} />;

  const today = todaysPlanDay(planState.plan);
  return (
    <div className="space-y-3">
      <TodayPreview day={today} onOpen={() => setOpen(true)}>
        <WorkoutDay day={today} compact />
      </TodayPreview>
      <div className="flex justify-end">
        <button onClick={planState.generate} className="text-xs text-neutral-500 hover:text-white transition-colors">
          ↻ Regenerate
        </button>
      </div>
      {open && (
        <PlanModal
          title="Workout Plan"
          plan={planState.plan}
          renderDay={day => <WorkoutDay day={day} />}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}

function MealPlanContent({ planState }) {
  const [open, setOpen] = useState(false);
  if (planState.status !== 'ready') return <PlanStatus planState={planState} />;

  const plan = planState.plan;
  const today = todaysPlanDay(plan);
  const target = plan.dailyCalories != null && (
    <p className="text-xs text-neutral-500">
      Daily target: ~{plan.dailyCalories} kcal &middot; ~{plan.dailyProteinG}g protein
    </p>
  );
  return (
    <div className="space-y-3">
      {target}
      <TodayPreview day={today} onOpen={() => setOpen(true)}>
        <MealDay day={today} compact />
      </TodayPreview>
      {open && (
        <PlanModal
          title="Meal Plan"
          plan={plan}
          header={target}
          renderDay={day => <MealDay day={day} />}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}

// Gemini's chat replies use a little Markdown (**bold** and "* " bullet points).
// Show them properly instead of as raw symbols - no extra library needed.
function FormattedText({ text }) {
  return text.split('\n').map((line, i) => {
    const isBullet = /^\s*[*-]\s+/.test(line);
    const content = isBullet ? line.replace(/^\s*[*-]\s+/, '') : line;
    const parts = content.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
      part.startsWith('**') && part.endsWith('**') && part.length > 4
        ? <strong key={j} className="text-white font-semibold">{part.slice(2, -2)}</strong>
        : part
    );
    return (
      <div key={i} className={isBullet ? 'pl-4 -indent-3' : ''}>
        {isBullet && '\u2022 '}{parts}{line === '' && '\u00A0'}
      </div>
    );
  });
}

// One-tap starter questions, shown until the user sends their first message.
const CHAT_SUGGESTIONS = [
  'What am I training today?',
  'What should I eat today?',
  'Summarise my last report',
];

function ChatCard({ onWorkoutPlan, onMealPlan }) {
  // Kept in a ref: the socket's onmessage handler is created once, so it must read
  // the latest callbacks rather than the ones from the first render.
  const planCallbacksRef = useRef({ onWorkoutPlan, onMealPlan });
  planCallbacksRef.current = { onWorkoutPlan, onMealPlan };
  const [messages, setMessages] = useState([
    { role: 'assistant', text: "Hey! Ask me about your form, recovery, past reports, or what to train next." },
  ]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState('idle'); // 'idle' | 'connecting' | 'sending'
  const wsRef = useRef(null);
  const listRef = useRef(null);
  const statusRef = useRef(status);
  const pendingTimeoutRef = useRef(null);

  useEffect(() => { statusRef.current = status; }, [status]);

  const clearPendingTimeout = () => {
    if (pendingTimeoutRef.current) {
      clearTimeout(pendingTimeoutRef.current);
      pendingTimeoutRef.current = null;
    }
  };

  // One WS connection per Dashboard mount, opened lazily on the first message (not on
  // page load) - mirrors WorkoutView's "don't connect until needed" rule. It has to stay
  // open across messages, not reconnect each time: the backend keeps this chat's memory
  // and tool access tied to the connection itself, so a fresh socket would mean amnesia.
  useEffect(() => {
    return () => { clearPendingTimeout(); if (wsRef.current) wsRef.current.close(); };
  }, []);

  useEffect(() => {
    // Scroll only the message list - scrollIntoView also scrolled the whole page.
    const list = listRef.current;
    if (list) list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' });
  }, [messages, status]);

  const ensureSocket = () => new Promise((resolve, reject) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      resolve(wsRef.current);
      return;
    }
    const socket = new WebSocket('ws://localhost:8000');
    wsRef.current = socket;
    socket.onopen = () => resolve(socket);
    socket.onerror = () => reject(new Error('connect failed'));
    socket.onclose = () => {
      wsRef.current = null;
      // Only surface this if we were mid-request - a close after an idle chat (e.g. the
      // user navigated away and back) isn't worth interrupting them about.
      if (statusRef.current !== 'idle') {
        clearPendingTimeout();
        setMessages(prev => [...prev, { role: 'assistant', text: 'Connection to the AI Engine was lost - try sending that again.' }]);
        setStatus('idle');
      }
    };
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.action === 'chat_reply') {
        clearPendingTimeout();
        // The chat made a new plan -> put it on the dashboard card too.
        if (data.workout_plan) planCallbacksRef.current.onWorkoutPlan?.(data.workout_plan);
        if (data.meal_plan) planCallbacksRef.current.onMealPlan?.(data.meal_plan);
        setMessages(prev => [...prev, { role: 'assistant', text: data.reply }]);
        setStatus('idle');
      } else if (data.action === 'chat_error') {
        clearPendingTimeout();
        setMessages(prev => [...prev, { role: 'assistant', text: `Sorry, something went wrong: ${data.message}` }]);
        setStatus('idle');
      }
      // Any other message shape (e.g. a stale backend that doesn't recognize the "chat"
      // action yet) is ignored here - the timeout below turns that into a visible error
      // instead of leaving the UI stuck on "Thinking..." forever with no way out.
    };
  });

  // Called with a string when a suggestion is tapped, otherwise sends the text box.
  const sendMessage = async (preset) => {
    const text = (typeof preset === 'string' ? preset : input).trim();
    if (!text || status !== 'idle') return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', text }]);

    let profile = null;
    try {
      const raw = localStorage.getItem('fitness_profile');
      profile = raw ? JSON.parse(raw) : null;
    } catch {
      profile = null;
    }
    // Whatever's already generated and sitting on the dashboard right now - so the coach
    // can answer "what should I eat today" from the real cached plan instead of only
    // being able to trigger a fresh (slow, paid) regeneration.
    let workoutPlan = null;
    try {
      const raw = localStorage.getItem('fitness_workout_plan');
      workoutPlan = raw ? JSON.parse(raw).plan : null;
    } catch {
      workoutPlan = null;
    }
    let mealPlan = null;
    try {
      const raw = localStorage.getItem('fitness_meal_plan');
      mealPlan = raw ? JSON.parse(raw).plan : null;
    } catch {
      mealPlan = null;
    }
    const sessionId = localStorage.getItem('fitness_session_id');

    setStatus(wsRef.current?.readyState === WebSocket.OPEN ? 'sending' : 'connecting');
    try {
      const socket = await ensureSocket();
      setStatus('sending');
      socket.send(JSON.stringify({
        action: 'chat', message: text, profile, session_id: sessionId,
        workout_plan: workoutPlan, meal_plan: mealPlan,
      }));
      clearPendingTimeout();
      pendingTimeoutRef.current = setTimeout(() => {
        setMessages(prev => [...prev, {
          role: 'assistant',
          text: "No response after 90s - the AI Engine may not be running, or Google's servers are very busy. Try again?",
        }]);
        setStatus('idle');
      }, 90000);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', text: "Couldn't reach the AI Engine - make sure the backend is running." }]);
      setStatus('idle');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <GlassCard className="flex flex-col h-[34rem]">
      {/* Header */}
      <div className="flex items-center gap-3 pb-4 mb-4 border-b border-white/10 shrink-0">
        <div className="w-9 h-9 rounded-full bg-white text-black flex items-center justify-center text-sm font-bold">&#10022;</div>
        <div>
          <h3 className="text-sm font-semibold text-white">GymBro</h3>
          <p className="text-xs text-neutral-500">Ask about your plan, meals, form or past reports</p>
        </div>
      </div>

      {/* Messages - the only part that scrolls */}
      <div
        ref={listRef}
        className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-3 pr-1 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.2)_transparent]"
      >
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed max-w-[88%] ${
                m.role === 'user'
                  ? 'bg-white text-black rounded-br-md whitespace-pre-wrap'
                  : 'bg-white/[0.05] border border-white/10 text-neutral-200 rounded-bl-md'
              }`}
            >
              {m.role === 'assistant' ? <FormattedText text={m.text} /> : m.text}
            </div>
          </div>
        ))}

        {/* Starter questions until the first message is sent */}
        {messages.length === 1 && status === 'idle' && (
          <div className="flex flex-wrap gap-2 mt-1">
            {CHAT_SUGGESTIONS.map(q => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                className="text-xs text-neutral-300 border border-white/15 rounded-full px-3 py-1.5 hover:bg-white/10 hover:text-white transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Typing indicator */}
        {status !== 'idle' && (
          <div className="flex justify-start">
            <div className="bg-white/[0.05] border border-white/10 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-1.5">
              {status === 'connecting' ? (
                <span className="text-xs text-neutral-500">Connecting...</span>
              ) : (
                [0, 150, 300].map(delay => (
                  <span
                    key={delay}
                    className="w-1.5 h-1.5 rounded-full bg-neutral-400 animate-bounce"
                    style={{ animationDelay: `${delay}ms` }}
                  />
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Text box - always visible at the bottom of the card */}
      <div className="flex items-center gap-2 mt-4 shrink-0 bg-white/[0.04] border border-white/10 rounded-full pl-4 pr-1.5 py-1.5 focus-within:border-white/30 transition-colors">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message GymBro..."
          className="flex-1 bg-transparent text-sm text-white placeholder-neutral-500 focus:outline-none"
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || status !== 'idle'}
          aria-label="Send message"
          className="w-8 h-8 shrink-0 rounded-full bg-white text-black flex items-center justify-center disabled:bg-white/10 disabled:text-neutral-500 disabled:cursor-not-allowed transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
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
            <div key={report.filename} className="flex items-center justify-between gap-3 bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3 hover:bg-white/[0.05] transition-colors">
              <div className="min-w-0">
                <p className="text-sm font-medium text-white">Workout report</p>
                <p className="text-xs text-neutral-500 mt-0.5">
                  {new Date(report.created_at * 1000).toLocaleString(undefined, {
                    weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
                  })}
                </p>
              </div>
              <button
                onClick={() => downloadReport(report.filename)}
                className="shrink-0 text-xs font-semibold text-white border border-white/15 rounded-full px-3.5 py-1.5 hover:bg-white hover:text-black transition-colors"
              >
                &darr; Download
              </button>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  );
}

function Dashboard({ onStartWorkout }) {
  const { profile, updateProfile, clearProfile, recordNewStats, history, deleteHistoryEntry, clearHistory } = useFitnessProfile();
  const workoutPlanState = useWorkoutPlan(profile);
  const mealPlanState = useMealPlan(profile);
  const [profileMode, setProfileMode] = useState(profile ? null : 'edit');

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
          <p className="text-neutral-500 mt-1.5">
            {new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })} &middot; Ready to train?
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:items-stretch">

          {/* Main column */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            {/* Start Workout CTA */}
            <button
              onClick={onStartWorkout}
              className="group w-full rounded-[28px] p-8 text-left bg-white text-black hover:bg-neutral-100 transition-colors duration-300 shadow-[0_0_60px_-15px_rgba(255,255,255,0.25)] flex items-center justify-between gap-6"
            >
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-neutral-500">Ready when you are</p>
                <h2 className="text-3xl font-semibold tracking-tight mt-1">Start Workout</h2>
                <p className="text-neutral-600 mt-1">Track squats, pushups, planks and more with real-time AI form coaching</p>
                <div className="flex flex-wrap gap-2 mt-4">
                  {['Live form feedback', 'Voice coaching', 'Rep counting', 'Injury report'].map(tag => (
                    <span key={tag} className="text-xs font-medium text-neutral-700 bg-black/[0.06] rounded-full px-3 py-1">{tag}</span>
                  ))}
                </div>
              </div>
              <span className="shrink-0 w-14 h-14 rounded-full bg-black text-white flex items-center justify-center text-xl transition-transform duration-300 group-hover:translate-x-1">
                &rarr;
              </span>
            </button>

            <GlassCard>
              <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-3">Your Profile</h3>
              <FitnessProfileGate
                profile={profile}
                updateProfile={updateProfile}
                clearProfile={clearProfile}
                recordNewStats={recordNewStats}
                mode={profileMode}
                setMode={setProfileMode}
                history={history}
                deleteHistoryEntry={deleteHistoryEntry}
                clearHistory={clearHistory}
              />
            </GlassCard>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <GlassCard>
                <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-3">Today's Workout</h3>
                {profile ? (
                  <WorkoutPlanContent planState={workoutPlanState} />
                ) : (
                  <p className="text-neutral-500 text-sm">Set up your profile above to see your personalized workout plan.</p>
                )}
              </GlassCard>

              <GlassCard>
                <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-3">Meal Prep</h3>
                {profile ? (
                  <MealPlanContent planState={mealPlanState} />
                ) : (
                  <p className="text-neutral-500 text-sm">Set up your profile above to see your AI-generated meal plan.</p>
                )}
              </GlassCard>
            </div>

            <PastReportsCard />
          </div>

          {/* Side column - the chat has a fixed height and stays in view (sticky) while
              the dashboard scrolls; only its message list scrolls, so the text box is
              always visible. */}
          <div className="flex flex-col gap-6 lg:sticky lg:top-10 lg:self-start">
            
            <ChatCard
              onWorkoutPlan={workoutPlanState.replaceWith}
              onMealPlan={mealPlanState.replaceWith}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
