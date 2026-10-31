import React, { useEffect, useRef, useState } from 'react';
import SummaryScreen from './SummaryScreen';
// MediaPipe is loaded via CDN in index.html to avoid Vite ESM compatibility issues
const { Pose, POSE_CONNECTIONS } = window;
const { Camera } = window;
const { drawConnectors, drawLandmarks } = window;

// The exercise list and which of them count reps are fetched from the backend
// (GET /exercises), which derives both from the exercise specs themselves - so
// this UI cannot drift out of sync with what the engine actually supports.
// These constants are only a fallback for when that fetch fails (server not up
// yet, offline reload), so the picker is never empty.
const DEFAULT_EXERCISES = [
  { id: "SQUAT", name: "Squats" },
  { id: "PLANK", name: "Planks" },
  { id: "DIP", name: "Tricep Dips" },
  { id: "PUSHUP", name: "Pushups" },
  { id: "PULLUP", name: "Pullups" },
  { id: "TWIST", name: "Russian Twists" },
  { id: "BICEP", name: "Bicep Curls" },
  { id: "HAMMER", name: "Hammer Curls" },
  { id: "LATERAL", name: "Lateral Raises" },
  { id: "PRESS", name: "Shoulder Press" },
  { id: "RDL", name: "Romanian Deadlift" },
  { id: "HIPTHRUST", name: "Hip Thrust" },
  { id: "PULLDOWN", name: "Lat Pulldown" },
  { id: "LEGEXT", name: "Leg Extension" },
  { id: "LEGRAISE", name: "Leg Raises" },
];

// Everything except the two hold-based exercises (Planks, Russian Twists).
const DEFAULT_REP_BASED = DEFAULT_EXERCISES
  .map(ex => ex.id)
  .filter(id => id !== "PLANK" && id !== "TWIST");

function formatDuration(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function downloadPdfFromBase64(filename, base64) {
  const byteChars = atob(base64);
  const byteNumbers = new Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
  const blob = new Blob([new Uint8Array(byteNumbers)], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// The engine colours its feedback in raw RGB (green / yellow / orange / red /
// white). On a light UI those are unreadable as text, so map them to the app's
// form-quality tones instead: good, careful, fix-this, or neutral coaching.
function feedbackTone(rgb) {
  const m = /rgb\((\d+),\s*(\d+),\s*(\d+)\)/.exec(rgb || '');
  const [r, g, b] = m ? m.slice(1).map(Number) : [255, 255, 255];
  if (g > 200 && r < 100) {
    return { label: 'Good form', icon: '\u2713', dot: 'bg-good', pill: 'bg-good-soft', labelText: 'text-good' };
  }
  if (r > 200 && g < 100) {
    return { label: 'Fix this now', icon: '!', dot: 'bg-bad', pill: 'bg-bad-soft', labelText: 'text-bad' };
  }
  if (r > 200 && b < 100) { // orange or yellow
    return { label: 'Careful', icon: '\u2022', dot: 'bg-warn', pill: 'bg-warn-soft', labelText: 'text-warn' };
  }
  return { label: 'Coach', icon: '\u2726', dot: 'bg-primary', pill: 'bg-surface', labelText: 'text-primary' };
}

// "KNEES CAVING IN! (PUSH OUT)" -> "Knees caving in! (push out)" - the engine
// shouts in capitals; sentence case reads friendlier and is easier to scan.
function friendlyFeedback(text) {
  const t = String(text || '');
  if (t !== t.toUpperCase()) return t;
  const lower = t.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function WorkoutView({ onExit }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);

  // No exercise is selected until the user starts a session and picks one from
  // the sidebar - the picker itself is disabled until then (see exercises.map below).
  const [mode, setMode] = useState(null);
  const [feedback, setFeedback] = useState("Loading AI Engine...");
  const [telemetry, setTelemetry] = useState([]);
  const [color, setColor] = useState("rgb(255, 255, 255)");
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(true);

  const [wsStatus, setWsStatus] = useState('connecting'); // 'connecting' | 'open' | 'reconnecting'

  const [sessionActive, setSessionActive] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [repCounts, setRepCounts] = useState({});
  const [plankHoldSeconds, setPlankHoldSeconds] = useState(0);
  const [reportStatus, setReportStatus] = useState('idle'); // 'idle' | 'generating' | 'error'
  const [reportError, setReportError] = useState('');

  const sessionStartRef = useRef(null);
  const sessionActiveRef = useRef(false);
  const modeRef = useRef(mode);
  const voiceEnabledRef = useRef(isVoiceEnabled);
  const preferredVoiceRef = useRef(null);
  // Durable per-workout id (survives a WS reconnect / page reload) - the backend's
  // mishap log is keyed by this, not by any one TCP connection.
  const sessionIdRef = useRef(typeof window !== 'undefined' ? localStorage.getItem('fitness_session_id') : null);

  const [exercises, setExercises] = useState(DEFAULT_EXERCISES);
  const [repBasedModes, setRepBasedModes] = useState(() => new Set(DEFAULT_REP_BASED));

  // Ask the engine what it actually supports. Failure is non-fatal - the
  // fallback list above stays in place.
  useEffect(() => {
    let cancelled = false;
    fetch('http://localhost:8000/exercises')
      .then(res => res.json())
      .then(data => {
        if (cancelled || !data?.exercises?.length) return;
        setExercises(data.exercises);
        setRepBasedModes(new Set(data.repBasedModes || []));
      })
      .catch(() => { /* server not up yet; fallback list is fine */ });
    return () => { cancelled = true; };
  }, []);

  // Correct-form guide + MuscleWiki demo video per exercise (GET /form-guide),
  // keyed here by engine mode id so the picker can link each exercise.
  const [formGuide, setFormGuide] = useState({});
  useEffect(() => {
    let cancelled = false;
    fetch('http://localhost:8000/form-guide')
      .then(res => res.json())
      .then(data => {
        if (cancelled || !data) return;
        const byMode = {};
        Object.values(data).forEach(entry => { if (entry.mode) byMode[entry.mode] = entry; });
        setFormGuide(byMode);
      })
      .catch(() => { /* optional - the checker works without it */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { voiceEnabledRef.current = isVoiceEnabled; }, [isVoiceEnabled]);
  useEffect(() => { sessionActiveRef.current = sessionActive; }, [sessionActive]);

  // Voices load asynchronously and vary by OS; pick a natural-sounding one once available
  // instead of leaving it to whatever default the browser happens to fall back to.
  useEffect(() => {
    const pickVoice = () => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) return;
      preferredVoiceRef.current =
        voices.find(v => /Samantha|Ava|Zoe|Google US English/i.test(v.name) && v.lang.startsWith('en')) ||
        voices.find(v => v.localService && v.lang.startsWith('en')) ||
        voices.find(v => v.lang.startsWith('en')) ||
        voices[0];
    };
    pickVoice();
    window.speechSynthesis.onvoiceschanged = pickVoice;
    return () => { window.speechSynthesis.onvoiceschanged = null; };
  }, []);

  // Speaks a cue chosen by the server's VoiceCoach (voice_coach.py). The server
  // already decides WHEN to talk (one cue per 5 s window, or at once for an
  // injury), so there is no per-frame debouncing here any more.
  const speakCue = (cue) => {
    if (!voiceEnabledRef.current || !cue?.text) return;
    const text = cue.text;

    // Cues are >= 2.5 s apart, so normally nothing is still speaking. If it is,
    // an urgent (injury) cue interrupts; anything else waits its turn.
    if (cue.urgent) window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    if (preferredVoiceRef.current) utterance.voice = preferredVoiceRef.current;
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const startWorkout = () => {
    const newSessionId = crypto.randomUUID();
    sessionIdRef.current = newSessionId;
    localStorage.setItem('fitness_session_id', newSessionId);

    setMode(null); // always re-enter the "choose an exercise" state for a fresh session
    setRepCounts({});
    setPlankHoldSeconds(0);
    setElapsedSeconds(0);
    setShowSummary(false);
    setReportStatus('idle');
    setReportError('');
    setSessionActive(true);
  };

  const endWorkout = () => {
    setSessionActive(false);
    setShowSummary(true);
  };

  const dismissSummary = () => {
    setShowSummary(false);
  };

  const generateReport = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setReportStatus('error');
      setReportError('Not connected to the AI Engine');
      return;
    }

    // Same 'fitness_profile' localStorage key the Dashboard reads/writes - lets the
    // report include a BMI/goal-aware health summary without prop-drilling it in.
    let profile = null;
    try {
      const raw = localStorage.getItem('fitness_profile');
      profile = raw ? JSON.parse(raw) : null;
    } catch {
      profile = null;
    }

    setReportStatus('generating');
    setReportError('');
    wsRef.current.send(JSON.stringify({
      action: 'generate_report',
      session_id: sessionIdRef.current,
      duration_seconds: elapsedSeconds,
      rep_counts: repCounts,
      plank_hold_seconds: plankHoldSeconds,
      profile,
    }));
  };

  // Workout duration timer
  useEffect(() => {
    if (!sessionActive) return;
    sessionStartRef.current = Date.now();
    const id = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - sessionStartRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [sessionActive]);

  // Effect A: WebSocket lifecycle (mount-once, independent of mode/voice/session state)
  useEffect(() => {
    let shouldReconnect = true;
    let socket;
    let reconnectTimer;

    const connect = () => {
      socket = new WebSocket('ws://localhost:8000');
      wsRef.current = socket;

      socket.onopen = () => {
        console.log('Connected to Python Fitness Engine');
        setWsStatus('open');
        setFeedback("Ready! Start a workout, then choose an exercise.");
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.action === 'report_ready') {
          downloadPdfFromBase64(data.filename, data.pdf_base64);
          setReportStatus('idle');
          return;
        }
        if (data.action === 'report_error') {
          setReportStatus('error');
          setReportError(data.message || 'Failed to generate report');
          return;
        }
        if (data.error) return;
        // Drop stale responses for an exercise the user has already switched away from
        if (data.mode !== undefined && data.mode !== modeRef.current) return;

        // On-screen text stays live per frame; the VOICE only speaks the
        // coach's windowed cue.
        if (data.feedback) setFeedback(data.feedback);
        if (data.voiceCue && sessionActiveRef.current) speakCue(data.voiceCue);
        if (data.telemetry) setTelemetry(data.telemetry);
        if (data.color) setColor(data.color);

        if (sessionActiveRef.current) {
          if (data.repCompleted) {
            setRepCounts(prev => ({ ...prev, [data.mode]: (prev[data.mode] || 0) + 1 }));
          }
          if (data.plankHoldDelta) {
            setPlankHoldSeconds(prev => prev + data.plankHoldDelta);
          }
        }
      };

      socket.onerror = () => {
        // onclose fires right after in browsers; let it drive the reconnect
      };

      socket.onclose = () => {
        wsRef.current = null;
        if (shouldReconnect) {
          setWsStatus('reconnecting');
          reconnectTimer = setTimeout(connect, 2000);
        }
      };
    };

    connect();

    return () => {
      shouldReconnect = false;
      clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, []);

  // Effect B: MediaPipe Pose + Camera setup (mount-once, independent of mode/voice)
  useEffect(() => {
    const pose = new Pose({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
    });

    pose.setOptions({
      modelComplexity: 1,
      smoothLandmarks: true,
      enableSegmentation: false,
      smoothSegmentation: false,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });

    pose.onResults((results) => {
      const videoWidth = videoRef.current.videoWidth;
      const videoHeight = videoRef.current.videoHeight;

      canvasRef.current.width = videoWidth;
      canvasRef.current.height = videoHeight;

      const ctx = canvasRef.current.getContext('2d');
      ctx.save();
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);

      if (results.poseLandmarks) {
        drawConnectors(ctx, results.poseLandmarks, POSE_CONNECTIONS, {
          color: '#A99BFF',
          lineWidth: 4,
        });
        drawLandmarks(ctx, results.poseLandmarks, {
          color: '#FFD15C',
          lineWidth: 2,
          radius: 4,
        });

        // No point sending frames before an exercise is chosen - the backend has no
        // analyzer to route a null mode to, and it'd just be wasted bandwidth.
        if (modeRef.current && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            mode: modeRef.current,
            landmarks: results.poseLandmarks,
            session_id: sessionIdRef.current
          }));
        }
      }
      ctx.restore();
    });

    let camera;
    if (videoRef.current) {
      camera = new Camera(videoRef.current, {
        onFrame: async () => {
          await pose.send({ image: videoRef.current });
        },
        width: 1280,
        height: 720,
      });
      camera.start();
    }

    return () => {
      if (camera) camera.stop();
      pose.close();
    };
  }, []);

  const tone = feedbackTone(color);
  const currentName = exercises.find(ex => ex.id === mode)?.name ?? mode;

  return (
    <div className="min-h-screen md:h-screen md:overflow-hidden bg-canvas text-ink font-sans flex flex-col md:flex-row">

      {/* Reconnect / connecting overlay */}
      {wsStatus !== 'open' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/90 backdrop-blur-sm">
          <div className="bg-surface border border-line rounded-3xl px-8 py-6 flex flex-col items-center gap-3 shadow-xl">
            <div className="h-8 w-8 rounded-full border-[3px] border-primary border-t-transparent animate-spin" />
            <p className="text-ink font-medium">
              {wsStatus === 'reconnecting' ? 'Reconnecting to the AI engine...' : 'Connecting to the AI engine...'}
            </p>
            <p className="text-sm text-muted">Make sure server.py is running.</p>
          </div>
        </div>
      )}

      {/* Workout summary screen */}
      {showSummary && (
        <SummaryScreen
          repCounts={repCounts}
          plankHoldSeconds={plankHoldSeconds}
          elapsedSeconds={elapsedSeconds}
          exercises={exercises}
          repBasedModes={repBasedModes}
          onDismiss={dismissSummary}
          onBackToDashboard={onExit}
          onGenerateReport={generateReport}
          reportStatus={reportStatus}
          reportError={reportError}
        />
      )}

      {/* Mobile top bar */}
      <div className="flex md:hidden items-center justify-between px-4 py-2.5 bg-surface/95 backdrop-blur border-b border-line fixed top-0 inset-x-0 z-30">
        <div className="flex items-center gap-2">
          {!sessionActive && (
            <button
              onClick={onExit}
              aria-label="Back to dashboard"
              className="w-9 h-9 rounded-full bg-tint border border-line flex items-center justify-center text-sm"
            >
              ←
            </button>
          )}
          <span className="text-sm font-semibold tracking-tight">
            {sessionActive && mode ? currentName : 'Workout'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={sessionActive ? endWorkout : startWorkout}
            className={`px-4 py-2 rounded-full text-xs font-semibold transition-colors tabular-nums ${sessionActive ? 'bg-bad text-white' : 'bg-sun text-ink'}`}
          >
            {sessionActive ? `End · ${formatDuration(elapsedSeconds)}` : 'Start workout'}
          </button>
          <button
            onClick={() => setIsVoiceEnabled(v => !v)}
            aria-label={isVoiceEnabled ? 'Turn voice coaching off' : 'Turn voice coaching on'}
            className="w-9 h-9 rounded-full bg-tint border border-line flex items-center justify-center text-sm"
          >
            {isVoiceEnabled ? '🔊' : '🔇'}
          </button>
        </div>
      </div>

      {/* Sidebar (desktop) */}
      <aside className="hidden md:flex md:flex-col md:w-80 shrink-0 bg-surface border-r border-line z-10">
        <div className="p-6 border-b border-line">
          <div className="flex items-center gap-3">
            {!sessionActive && (
              <button
                onClick={onExit}
                aria-label="Back to dashboard"
                className="w-9 h-9 shrink-0 rounded-full bg-tint border border-line hover:bg-primary-soft flex items-center justify-center text-sm transition-colors"
              >
                ←
              </button>
            )}
            <h1 className="text-xl font-semibold tracking-tight">
              {sessionActive ? 'Workout in progress' : 'Ready to train?'}
            </h1>
          </div>

          <button
            onClick={sessionActive ? endWorkout : startWorkout}
            className={`mt-5 w-full py-3 rounded-full font-semibold transition-colors ${
              sessionActive ? 'bg-bad hover:bg-bad/90 text-white' : 'bg-sun hover:bg-sun-deep text-ink'
            }`}
          >
            {sessionActive
              ? <>End workout <span className="tabular-nums font-normal opacity-90 ml-1">{formatDuration(elapsedSeconds)}</span></>
              : 'Start workout'}
          </button>
        </div>

        <div className="flex-1 p-6 overflow-y-auto">
          <h2 className="text-base font-semibold text-ink mb-1">Choose an exercise</h2>
          <p className="text-sm text-muted mb-4">
            {sessionActive ? 'Tap ▶ to watch how it should look.' : 'Start a workout first. You can watch the videos any time.'}
          </p>
          <div className="space-y-2">
            {exercises.map(ex => (
              <div key={ex.id} className="flex items-center gap-2">
                <button
                  onClick={() => setMode(ex.id)}
                  disabled={!sessionActive}
                  aria-pressed={mode === ex.id}
                  className={`flex-1 min-w-0 text-left px-4 py-2.5 rounded-2xl transition-colors border disabled:opacity-50 disabled:cursor-not-allowed ${
                    mode === ex.id
                      ? 'bg-primary border-primary text-white font-medium'
                      : 'bg-surface border-line hover:enabled:bg-primary-soft hover:enabled:border-primary/30 text-ink'
                  }`}
                >
                  {ex.name}
                </button>
                {/* Always clickable - you can watch the correct form before starting. */}
                {formGuide[ex.id]?.video && (
                  <a
                    href={formGuide[ex.id].video}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`Watch correct ${ex.name} form on MuscleWiki`}
                    aria-label={`Watch correct ${ex.name} form`}
                    className="shrink-0 w-10 h-10 rounded-full bg-sun/40 hover:bg-sun text-ink flex items-center justify-center transition-colors"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
                  </a>
                )}
              </div>
            ))}
          </div>

          {/* Quick reminder of good form for the exercise being tracked */}
          {mode && formGuide[mode] && (
            <div className="mt-6 bg-primary-soft rounded-2xl p-4 space-y-2">
              <h3 className="text-base font-semibold text-ink">How to do {currentName.toLowerCase()}</h3>
              <ol className="space-y-1.5">
                {formGuide[mode].execution.map((step, i) => (
                  <li key={i} className="flex gap-2 text-sm text-ink leading-snug">
                    <span className="shrink-0 w-5 h-5 rounded-full bg-surface text-primary text-[11px] font-semibold flex items-center justify-center">{i + 1}</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
              {formGuide[mode].video && (
                <a
                  href={formGuide[mode].video}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-sm font-semibold text-primary underline underline-offset-4 hover:text-primary-deep pt-1"
                >
                  Watch the video on MuscleWiki {'↗'}
                </a>
              )}
            </div>
          )}

          <div className="mt-8 pt-6 border-t border-line">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-ink">Voice coaching</span>
                <p className="text-xs text-muted">Speaks a tip every few seconds</p>
              </div>
              <button
                onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
                role="switch"
                aria-checked={isVoiceEnabled}
                aria-label="Voice coaching"
                className={`w-12 h-7 rounded-full transition-colors ${isVoiceEnabled ? 'bg-primary' : 'bg-line-strong'} relative shrink-0`}
              >
                <div className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow transition-transform ${isVoiceEnabled ? 'left-6' : 'left-1'}`} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main: camera in a rounded frame with light overlay cards */}
      <main className="flex-1 flex flex-col pt-14 pb-16 md:p-6 min-h-screen md:min-h-0">
        <div className="relative flex-1 bg-[#2A2745] md:rounded-[28px] overflow-hidden">
          {/* Video feed - mirrored (selfie-view) for display only; the raw,
              unmirrored frame is still what gets sent to MediaPipe/the backend,
              so landmark data and L/R labeling are unaffected. */}
          <video
            ref={videoRef}
            className="absolute inset-0 w-full h-full object-contain -scale-x-100"
            playsInline
            muted
          />

          {/* Canvas for skeletal lines - mirrored to match the video underneath */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full object-contain -scale-x-100"
          />

          {/* Overlays */}
          <div className="absolute inset-0 p-4 sm:p-6 pointer-events-none flex flex-col justify-between">

            {/* Top: rep counter (left) + camera readings (right) */}
            <div className="flex justify-between items-start gap-3">
              {sessionActive && mode ? (
                <div className="bg-surface rounded-3xl px-5 py-4 min-w-[150px] shadow-lg">
                  <p className="text-sm font-medium text-muted">{currentName}</p>
                  {mode === 'PLANK' ? (
                    <p className="mt-0.5">
                      <span className="text-6xl font-semibold tabular-nums leading-none text-primary">{Math.round(plankHoldSeconds)}</span>
                      <span className="text-base text-muted ml-1.5">sec</span>
                    </p>
                  ) : repBasedModes.has(mode) ? (
                    <p className="mt-0.5">
                      <span className="text-6xl font-semibold tabular-nums leading-none text-primary">{repCounts[mode] || 0}</span>
                      <span className="text-base text-muted ml-1.5">{(repCounts[mode] || 0) === 1 ? 'rep' : 'reps'}</span>
                    </p>
                  ) : (
                    <p className="text-base font-medium text-ink mt-1">Hold the position</p>
                  )}
                </div>
              ) : (
                <div className="bg-surface/95 rounded-3xl px-5 py-4 max-w-xs shadow-lg">
                  <p className="text-base font-semibold text-ink">
                    {sessionActive ? 'Pick an exercise to begin' : 'Press Start workout to begin'}
                  </p>
                  <p className="text-sm text-muted mt-0.5">Stand side-on so your whole body is in view.</p>
                </div>
              )}

              {telemetry.length > 0 && (
                <div className="bg-surface/90 rounded-2xl px-4 py-3 shadow-lg hidden sm:block">
                  <p className="text-xs font-medium text-muted mb-1">Camera readings</p>
                  {telemetry.map((stat, i) => (
                    <div key={i} className="text-sm tabular-nums text-ink">{stat}</div>
                  ))}
                </div>
              )}
            </div>

            {/* Bottom: live feedback, coloured by how the form looks */}
            <div className="flex justify-center mb-4 md:mb-2">
              <div
                role="status"
                aria-live="polite"
                className={`flex items-center gap-3 pl-3 pr-6 py-3 rounded-full shadow-xl transition-colors duration-300 ${tone.pill}`}
              >
                <span className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center text-white text-lg font-bold ${tone.dot}`} aria-hidden="true">
                  {tone.icon}
                </span>
                <span>
                  <span className={`block text-xs font-semibold ${tone.labelText}`}>{tone.label}</span>
                  <span className="block text-xl sm:text-2xl font-semibold tracking-tight text-ink">{friendlyFeedback(feedback)}</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Mobile bottom bar: exercise picker */}
      <div className="flex md:hidden fixed bottom-0 inset-x-0 z-30 bg-surface/95 backdrop-blur border-t border-line overflow-x-auto whitespace-nowrap px-3 py-2.5 gap-2">
        {!sessionActive && (
          <span className="inline-flex items-center px-2 text-xs text-muted shrink-0">Start a workout first</span>
        )}
        {exercises.map(ex => (
          <button
            key={ex.id}
            onClick={() => setMode(ex.id)}
            disabled={!sessionActive}
            className={`inline-block px-4 py-2 rounded-full text-xs font-semibold border disabled:opacity-50 disabled:cursor-not-allowed shrink-0 ${
              mode === ex.id ? 'bg-primary border-primary text-white' : 'bg-surface border-line text-ink'
            }`}
          >
            {ex.name}
          </button>
        ))}
      </div>
    </div>
  );
}

export default WorkoutView;
