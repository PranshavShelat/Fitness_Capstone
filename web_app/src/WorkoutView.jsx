import React, { useEffect, useRef, useState } from 'react';
import SummaryScreen from './SummaryScreen';
// MediaPipe is loaded via CDN in index.html to avoid Vite ESM compatibility issues
const { Pose, POSE_CONNECTIONS } = window;
const { Camera } = window;
const { drawConnectors, drawLandmarks } = window;

// mode -> (worked_stage, rest_stage), mirrors server.py's REP_TRANSITIONS.
// Only used here to know which exercises are rep-based (for the summary screen).
const REP_BASED_MODES = new Set(["SQUAT", "DIP", "PUSHUP", "PULLUP", "BICEP", "HAMMER", "LATERAL", "PRESS"]);

function formatDuration(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function WorkoutView({ onExit }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);

  const [mode, setMode] = useState("SQUAT");
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

  const sessionStartRef = useRef(null);
  const sessionActiveRef = useRef(false);
  const modeRef = useRef(mode);
  const voiceEnabledRef = useRef(isVoiceEnabled);
  const preferredVoiceRef = useRef(null);

  // Exercise definitions
  const exercises = [
    { id: "SQUAT", name: "Squats" },
    { id: "PLANK", name: "Planks" },
    { id: "DIP", name: "Tricep Dips" },
    { id: "PUSHUP", name: "Pushups" },
    { id: "PULLUP", name: "Pullups" },
    { id: "TWIST", name: "Russian Twists" },
    { id: "BICEP", name: "Bicep Curls" },
    { id: "HAMMER", name: "Hammer Curls" },
    { id: "LATERAL", name: "Lateral Raises" },
    { id: "PRESS", name: "Shoulder Press" }
  ];

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

  // Helper for voice feedback (debounce so it doesn't spam)
  const lastSpokenRef = useRef("");
  const speakFeedback = (text) => {
    if (!voiceEnabledRef.current || !text || text === lastSpokenRef.current) return;

    // Cancel whatever's still queued/speaking so voice never lags behind the current feedback
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    if (preferredVoiceRef.current) utterance.voice = preferredVoiceRef.current;
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
    lastSpokenRef.current = text;
  };

  const startWorkout = () => {
    setRepCounts({});
    setPlankHoldSeconds(0);
    setElapsedSeconds(0);
    setShowSummary(false);
    setSessionActive(true);
  };

  const endWorkout = () => {
    setSessionActive(false);
    setShowSummary(true);
  };

  const dismissSummary = () => {
    setShowSummary(false);
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
        setFeedback("Ready! Select an exercise and step back.");
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.error) return;
        // Drop stale responses for an exercise the user has already switched away from
        if (data.mode !== undefined && data.mode !== modeRef.current) return;

        if (data.feedback) {
          setFeedback(data.feedback);
          speakFeedback(data.feedback);
        }
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
          color: '#00FFFF',
          lineWidth: 4,
        });
        drawLandmarks(ctx, results.poseLandmarks, {
          color: '#FF0000',
          lineWidth: 2,
          radius: 4,
        });

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            mode: modeRef.current,
            landmarks: results.poseLandmarks
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

  return (
    <div className="min-h-screen bg-gray-950 text-white font-sans flex flex-col md:flex-row">

      {/* Reconnect / connecting overlay */}
      {wsStatus !== 'open' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/80 backdrop-blur-sm">
          <div className="bg-gray-900/80 border border-gray-700/50 rounded-2xl px-8 py-6 flex flex-col items-center gap-3">
            <div className="h-8 w-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
            <p className="text-cyan-100 font-semibold">
              {wsStatus === 'reconnecting' ? 'Reconnecting to AI Engine...' : 'Connecting to AI Engine...'}
            </p>
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
          repBasedModes={REP_BASED_MODES}
          onDismiss={dismissSummary}
          onBackToDashboard={onExit}
        />
      )}

      {/* Mobile top bar */}
      <div className="flex md:hidden items-center justify-between px-4 py-2 bg-gray-900/90 backdrop-blur border-b border-gray-800 fixed top-0 inset-x-0 z-30">
        <div className="flex items-center gap-2">
          {!sessionActive && (
            <button
              onClick={onExit}
              aria-label="Back to dashboard"
              className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-sm"
            >
              ←
            </button>
          )}
          <span className="text-sm font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">
            AI Fitness
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={sessionActive ? endWorkout : startWorkout}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${sessionActive ? 'bg-red-600 hover:bg-red-500' : 'bg-cyan-600 hover:bg-cyan-500'}`}
          >
            {sessionActive ? formatDuration(elapsedSeconds) : 'Start'}
          </button>
          <button
            onClick={() => setIsVoiceEnabled(v => !v)}
            aria-label="Toggle voice coaching"
            className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-sm"
          >
            {isVoiceEnabled ? '🔊' : '🔇'}
          </button>
        </div>
      </div>

      {/* Sidebar: Dashboard (desktop only) */}
      <div className="hidden md:flex md:flex-col md:w-80 bg-gray-900 border-r border-gray-800 shadow-2xl z-10">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center gap-3">
            {!sessionActive && (
              <button
                onClick={onExit}
                aria-label="Back to dashboard"
                className="w-8 h-8 shrink-0 rounded-full bg-gray-800 hover:bg-gray-700 flex items-center justify-center text-sm transition-colors"
              >
                ←
              </button>
            )}
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">
              AI Fitness Engine
            </h1>
          </div>
          <p className="text-gray-400 text-sm mt-2">Zero-Latency WebTracker</p>

          <button
            onClick={sessionActive ? endWorkout : startWorkout}
            className={`mt-4 w-full py-3 rounded-xl font-bold transition-colors ${sessionActive ? 'bg-red-600 hover:bg-red-500' : 'bg-cyan-600 hover:bg-cyan-500'}`}
          >
            {sessionActive ? `End Workout · ${formatDuration(elapsedSeconds)}` : 'Start Workout'}
          </button>
        </div>

        <div className="flex-1 p-6 overflow-y-auto">
          <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">Select Exercise</h2>
          <div className="space-y-2">
            {exercises.map(ex => (
              <button
                key={ex.id}
                onClick={() => setMode(ex.id)}
                className={`w-full text-left px-4 py-3 rounded-xl transition-all duration-200 border ${
                  mode === ex.id
                    ? 'bg-cyan-900/30 border-cyan-500/50 text-cyan-300'
                    : 'bg-gray-800/50 border-gray-700 hover:bg-gray-700 text-gray-300'
                }`}
              >
                {ex.name}
              </button>
            ))}
          </div>

          <div className="mt-8 pt-6 border-t border-gray-800">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">AI Voice Coaching</span>
              <button
                onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
                className={`w-12 h-6 rounded-full transition-colors ${isVoiceEnabled ? 'bg-cyan-500' : 'bg-gray-700'} relative`}
              >
                <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${isVoiceEnabled ? 'left-7' : 'left-1'}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content: Camera & UI Overlay */}
      <div className="flex-1 relative bg-black overflow-hidden flex flex-col pt-12 pb-16 md:pt-0 md:pb-0">
        {/* Video feed (hidden underneath) */}
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-contain opacity-70"
          playsInline
          muted
        />

        {/* Canvas for skeletal lines */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full object-contain"
        />

        {/* Glassmorphic UI Overlays */}
        <div className="absolute inset-0 p-6 pointer-events-none flex flex-col justify-between">

          {/* Top Panel: Telemetry */}
          <div className="flex justify-end">
            <div className="bg-gray-900/60 backdrop-blur-md border border-gray-700/50 rounded-2xl p-4 min-w-[200px]">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Live Metrics</h3>
              {telemetry.length > 0 ? (
                telemetry.map((stat, i) => (
                  <div key={i} className="text-sm font-mono text-cyan-100 mb-1">
                    {stat}
                  </div>
                ))
              ) : (
                <div className="text-sm text-gray-500 italic">No telemetry data...</div>
              )}
            </div>
          </div>

          {/* Bottom Panel: Dynamic Feedback */}
          <div className="flex justify-center mb-24 md:mb-10">
            <div
              className="px-8 py-4 rounded-full border shadow-2xl transition-all duration-300 backdrop-blur-md"
              style={{
                backgroundColor: 'rgba(17, 24, 39, 0.8)',
                borderColor: color,
                boxShadow: `0 0 20px ${color.replace(')', ', 0.2)').replace('rgb', 'rgba')}`
              }}
            >
              <h2 className="text-3xl font-bold tracking-wide" style={{ color: color }}>
                {feedback}
              </h2>
            </div>
          </div>
        </div>

      </div>

      {/* Mobile bottom bar: exercise picker */}
      <div className="flex md:hidden fixed bottom-0 inset-x-0 z-30 bg-gray-900/90 backdrop-blur border-t border-gray-800 overflow-x-auto whitespace-nowrap px-3 py-2 gap-2">
        {exercises.map(ex => (
          <button
            key={ex.id}
            onClick={() => setMode(ex.id)}
            className={`inline-block px-4 py-2 mr-2 rounded-full text-xs font-semibold border ${
              mode === ex.id ? 'bg-cyan-900/40 border-cyan-500/50 text-cyan-300' : 'bg-gray-800/60 border-gray-700 text-gray-300'
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
