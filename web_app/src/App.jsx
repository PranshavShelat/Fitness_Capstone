import React, { useEffect, useRef, useState } from 'react';
// MediaPipe is loaded via CDN in index.html to avoid Vite ESM compatibility issues
const { Pose, POSE_CONNECTIONS } = window;
const { Camera } = window;
const { drawConnectors, drawLandmarks } = window;

function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);

  const [mode, setMode] = useState("SQUAT");
  const [feedback, setFeedback] = useState("Loading AI Engine...");
  const [telemetry, setTelemetry] = useState([]);
  const [color, setColor] = useState("rgb(255, 255, 255)");
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(true);

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

  // Helper for voice feedback (debounce so it doesn't spam)
  const lastSpokenRef = useRef("");
  const speakFeedback = (text) => {
    if (!isVoiceEnabled || !text || text === lastSpokenRef.current) return;
    
    // Optional: Only speak critical feedback (e.g., if it changes significantly)
    // To keep it perfectly like Python, we just speak when the feedback string changes.
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1; // Slightly faster for workout energy
    window.speechSynthesis.speak(utterance);
    lastSpokenRef.current = text;
  };

  useEffect(() => {
    // 1. Initialize WebSocket
    wsRef.current = new WebSocket('ws://localhost:8000');
    
    wsRef.current.onopen = () => {
      console.log('Connected to Python Fitness Engine');
      setFeedback("Ready! Select an exercise and step back.");
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.error) return;

      if (data.feedback) {
        setFeedback(data.feedback);
        speakFeedback(data.feedback);
      }
      if (data.telemetry) setTelemetry(data.telemetry);
      if (data.color) setColor(data.color);
    };

    // 2. Initialize MediaPipe Pose
    const pose = new Pose({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
    });

    pose.setOptions({
      modelComplexity: 1,
      smoothLandmarks: true, // Native smoothing is incredible in browser
      enableSegmentation: false,
      smoothSegmentation: false,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });

    pose.onResults((results) => {
      const videoWidth = videoRef.current.videoWidth;
      const videoHeight = videoRef.current.videoHeight;
      
      // Set canvas size to match video
      canvasRef.current.width = videoWidth;
      canvasRef.current.height = videoHeight;
      
      const ctx = canvasRef.current.getContext('2d');
      ctx.save();
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);

      // Draw the beautiful skeletal lines
      if (results.poseLandmarks) {
        drawConnectors(ctx, results.poseLandmarks, POSE_CONNECTIONS, {
          color: '#00FFFF', // Cyan modern lines
          lineWidth: 4,
        });
        drawLandmarks(ctx, results.poseLandmarks, {
          color: '#FF0000', // Red dots
          lineWidth: 2,
          radius: 4,
        });

        // Send to Python Engine via WebSocket
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          // Add a simple throttle to not spam the server (e.g. 30fps max)
          wsRef.current.send(JSON.stringify({
            mode: mode,
            landmarks: results.poseLandmarks
          }));
        }
      }
      ctx.restore();
    });

    // 3. Initialize Webcam
    if (videoRef.current) {
      const camera = new Camera(videoRef.current, {
        onFrame: async () => {
          await pose.send({ image: videoRef.current });
        },
        width: 1280,
        height: 720,
      });
      camera.start();
    }

    return () => {
      wsRef.current?.close();
      pose.close();
    };
  }, [mode, isVoiceEnabled]); // Re-bind if mode changes (or handle it smoothly via ref)

  return (
    <div className="min-h-screen bg-gray-950 text-white font-sans flex flex-col md:flex-row">
      
      {/* Sidebar: Dashboard */}
      <div className="w-full md:w-80 bg-gray-900 border-r border-gray-800 flex flex-col shadow-2xl z-10">
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">
            AI Fitness Engine
          </h1>
          <p className="text-gray-400 text-sm mt-2">Zero-Latency WebTracker</p>
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
      <div className="flex-1 relative bg-black overflow-hidden flex flex-col">
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
          <div className="flex justify-center mb-10">
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
    </div>
  );
}

export default App;
