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

function FitnessProfileForm({ initial, onSave, onCancel }) {
  const [heightCm, setHeightCm] = useState(initial?.heightCm ?? '');
  const [weightKg, setWeightKg] = useState(initial?.weightKg ?? '');
  const [goal, setGoal] = useState(initial?.goal ?? 'MAINTAIN');
  const [diet, setDiet] = useState(initial?.diet ?? null);
  const [eatsEggs, setEatsEggs] = useState(initial?.eatsEggs ?? null);

  const dietResolved = diet === 'NON_VEG' || (diet === 'VEG' && eatsEggs !== null);
  const canSave = Number(heightCm) > 0 && Number(weightKg) > 0 && dietResolved;

  return (
    <div className="space-y-3 mb-4">
      <div className="grid grid-cols-2 gap-3">
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
          onClick={() => onSave({ heightCm: Number(heightCm), weightKg: Number(weightKg), goal, diet, eatsEggs: diet === 'VEG' ? eatsEggs : null })}
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

function FitnessProfileSummary({ profile, onEdit, onRecordNew, onClearProfile, history, onDeleteHistoryEntry, onClearHistory }) {
  const [showTimeline, setShowTimeline] = useState(false);
  const [confirmingClearProfile, setConfirmingClearProfile] = useState(false);
  const heightM = profile.heightCm / 100;
  const bmi = profile.weightKg / (heightM * heightM);
  const goalLabel = GOALS.find(g => g.id === profile.goal)?.label ?? profile.goal;

  return (
    <div>
      <div className="flex items-center justify-between bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3">
        <div>
          <p className="text-lg font-semibold tracking-tight">
            BMI {bmi.toFixed(1)} <span className="text-neutral-500 text-sm font-normal">&middot; {bmiCategory(bmi)}</span>
          </p>
          <p className="text-sm text-neutral-400">Goal: {goalLabel} &middot; {dietLabel(profile)}</p>
        </div>
        {confirmingClearProfile ? (
          <div className="flex items-center gap-3 shrink-0">
            <span className="text-xs text-neutral-500">Clear your profile?</span>
            <button
              onClick={() => setConfirmingClearProfile(false)}
              className="text-xs text-neutral-500 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => { onClearProfile(); setConfirmingClearProfile(false); }}
              className="text-xs text-red-400 hover:text-red-300 transition-colors"
            >
              Confirm Clear
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3 shrink-0">
            <button onClick={() => setShowTimeline(true)} className="text-xs text-neutral-500 hover:text-white transition-colors">
              View Timeline
            </button>
            <button onClick={onRecordNew} className="text-xs text-neutral-500 hover:text-white transition-colors">
              Record New Stats
            </button>
            <button onClick={onEdit} className="text-xs text-neutral-500 hover:text-white transition-colors">
              Edit
            </button>
            <button onClick={() => setConfirmingClearProfile(true)} className="text-xs text-neutral-500 hover:text-white transition-colors">
              Clear
            </button>
          </div>
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

const PLAN_STORAGE_KEY = 'fitness_plan';
const WEEKDAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function profileKey(profile) {
  return profile
    ? `${profile.heightCm}-${profile.weightKg}-${profile.goal}-${dietCategory(profile)}`
    : null;
}

function loadCachedPlan() {
  try {
    const raw = localStorage.getItem(PLAN_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function todaysPlanDay(plan) {
  const todayName = WEEKDAY_NAMES[new Date().getDay()];
  return plan.days.find(d => d.day === todayName) ?? plan.days[0];
}

// Shared across both the Today's Workout and Meal Prep cards - one generated
// plan drives both, cached in localStorage keyed to the exact profile it was
// generated for so an unrelated re-render never triggers a fresh (slow, paid)
// Gemini call, only an actual height/weight/goal change does.
function useFitnessPlan(profile) {
  const key = profileKey(profile);
  const [state, setState] = useState(() => {
    const cached = loadCachedPlan();
    return cached && cached.profileKey === key
      ? { status: 'ready', plan: cached.plan }
      : { status: 'idle', plan: null };
  });

  useEffect(() => {
    const cached = loadCachedPlan();
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
      const params = new URLSearchParams({
        height: profile.heightCm,
        weight: profile.weightKg,
        goal: profile.goal,
        diet: dietCategory(profile),
      });
      const res = await fetch(`http://localhost:8000/plan?${params}`);
      if (!res.ok) throw new Error('Plan request failed');
      const plan = await res.json();
      localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify({ profileKey: key, plan }));
      setState({ status: 'ready', plan });
    } catch {
      setState({ status: 'error', plan: null });
    }
  };

  return { ...state, generate };
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

function WorkoutPlanContent({ planState }) {
  const [expanded, setExpanded] = useState(false);

  if (planState.status === 'idle') return <GeneratePlanButton onClick={planState.generate} />;
  if (planState.status === 'loading') {
    return <p className="text-neutral-500 text-sm italic">Building your personalized plan with AI - this can take up to 30s...</p>;
  }
  if (planState.status === 'error') {
    return (
      <div className="space-y-2">
        <p className="text-neutral-500 text-sm">Couldn't generate a plan - is the AI Engine running?</p>
        <button onClick={planState.generate} className="text-xs text-white underline">Try again</button>
      </div>
    );
  }

  const today = todaysPlanDay(planState.plan);
  const daysToShow = expanded ? planState.plan.days : [today];

  return (
    <div className="space-y-3">
      <div className="space-y-2 max-h-64 overflow-y-auto pr-1 -mr-1">
        {daysToShow.map(day => (
          <div key={day.day} className="bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3">
            <p className="text-sm font-semibold mb-1.5">
              {day.day}{!expanded && day.day === today.day ? ' (Today)' : ''}
            </p>
            {day.workout.is_rest ? (
              <p className="text-sm text-neutral-400">Rest day</p>
            ) : (
              <ul className="text-sm text-neutral-300 space-y-0.5">
                {day.workout.exercises.map((ex, i) => (
                  <li key={i}>{ex.name} &mdash; {ex.sets_reps}</li>
                ))}
              </ul>
            )}
            {day.notes && <p className="text-xs text-neutral-500 mt-1.5 italic">{day.notes}</p>}
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <button onClick={() => setExpanded(e => !e)} className="text-xs text-neutral-500 hover:text-white transition-colors">
          {expanded ? 'Show today only' : 'View full week'}
        </button>
        <button onClick={planState.generate} className="text-xs text-neutral-500 hover:text-white transition-colors">
          ↻ Regenerate
        </button>
      </div>
      <SourcesFooter sources={planState.plan.sources} />
    </div>
  );
}

function MealPlanContent({ planState }) {
  const [expanded, setExpanded] = useState(false);

  if (planState.status === 'idle') return <GeneratePlanButton onClick={planState.generate} />;
  if (planState.status === 'loading') {
    return <p className="text-neutral-500 text-sm italic">Building your personalized plan with AI - this can take up to 30s...</p>;
  }
  if (planState.status === 'error') {
    return (
      <div className="space-y-2">
        <p className="text-neutral-500 text-sm">Couldn't generate a plan - is the AI Engine running?</p>
        <button onClick={planState.generate} className="text-xs text-white underline">Try again</button>
      </div>
    );
  }

  const today = todaysPlanDay(planState.plan);
  const daysToShow = expanded ? planState.plan.days : [today];

  return (
    <div className="space-y-3">
      <div className="space-y-2 max-h-64 overflow-y-auto pr-1 -mr-1">
        {daysToShow.map(day => (
          <div key={day.day} className="bg-white/[0.03] border border-white/5 rounded-2xl px-4 py-3">
            <p className="text-sm font-semibold mb-1.5">
              {day.day}{!expanded && day.day === today.day ? ' (Today)' : ''}
            </p>
            <ul className="text-sm text-neutral-300 space-y-1">
              <li><span className="text-neutral-500">Breakfast:</span> {day.meals.breakfast}</li>
              <li><span className="text-neutral-500">Lunch:</span> {day.meals.lunch}</li>
              <li><span className="text-neutral-500">Dinner:</span> {day.meals.dinner}</li>
              <li><span className="text-neutral-500">Snack:</span> {day.meals.snack}</li>
            </ul>
          </div>
        ))}
      </div>
      <button onClick={() => setExpanded(e => !e)} className="text-xs text-neutral-500 hover:text-white transition-colors">
        {expanded ? 'Show today only' : 'View full week'}
      </button>
      <SourcesFooter sources={planState.plan.sources} />
    </div>
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
  const { profile, updateProfile, clearProfile, recordNewStats, history, deleteHistoryEntry, clearHistory } = useFitnessProfile();
  const planState = useFitnessPlan(profile);
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
                  <WorkoutPlanContent planState={planState} />
                ) : (
                  <p className="text-neutral-500 text-sm">Set up your profile above to see your personalized workout plan.</p>
                )}
              </GlassCard>

              <GlassCard>
                <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-3">Meal Prep</h3>
                {profile ? (
                  <MealPlanContent planState={planState} />
                ) : (
                  <p className="text-neutral-500 text-sm">Set up your profile above to see your AI-generated meal plan.</p>
                )}
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
