import React from 'react';

function formatDuration(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function SummaryScreen({ repCounts, plankHoldSeconds, elapsedSeconds, exercises, repBasedModes, onDismiss, onBackToDashboard }) {
  const repExercises = exercises.filter(ex => repBasedModes.has(ex.id));
  const totalReps = Object.values(repCounts).reduce((sum, n) => sum + n, 0);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-gray-950/90 backdrop-blur-md p-6">
      <div className="w-full max-w-md bg-gray-900/60 backdrop-blur-md border border-gray-700/50 rounded-2xl p-8 shadow-2xl">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Workout Complete</h2>
        <p className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 mb-6">
          {formatDuration(elapsedSeconds)}
        </p>

        <div className="space-y-2 mb-6">
          {repExercises.map(ex => (
            <div key={ex.id} className="flex items-center justify-between text-sm">
              <span className="text-gray-300">{ex.name}</span>
              <span className="font-mono text-cyan-100">{repCounts[ex.id] || 0} reps</span>
            </div>
          ))}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-300">Plank Hold</span>
            <span className="font-mono text-cyan-100">{Math.round(plankHoldSeconds)}s</span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-gray-800 mb-6">
          <span className="text-sm font-bold text-gray-400 uppercase tracking-wider">Total Reps</span>
          <span className="text-xl font-bold text-cyan-300">{totalReps}</span>
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={onDismiss}
            className="w-full py-3 rounded-xl font-bold bg-cyan-600 hover:bg-cyan-500 transition-colors"
          >
            Start New Workout
          </button>
          <button
            onClick={onBackToDashboard}
            className="w-full py-3 rounded-xl font-semibold bg-transparent border border-gray-700 text-gray-300 hover:bg-gray-800/50 transition-colors"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

export default SummaryScreen;
