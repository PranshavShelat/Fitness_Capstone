import React from 'react';

function formatDuration(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function SummaryScreen({ repCounts, plankHoldSeconds, elapsedSeconds, exercises, repBasedModes, onDismiss, onBackToDashboard, onGenerateReport, reportStatus, reportError }) {
  const repExercises = exercises.filter(ex => repBasedModes.has(ex.id));
  const totalReps = Object.values(repCounts).reduce((sum, n) => sum + n, 0);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/90 backdrop-blur-md p-6">
      <div className="w-full max-w-md bg-white/[0.04] backdrop-blur-2xl border border-white/10 rounded-[28px] p-8 shadow-2xl">
        <h2 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em] mb-1">Workout Complete</h2>
        <p className="text-4xl font-semibold tracking-tight mb-6">
          {formatDuration(elapsedSeconds)}
        </p>

        <div className="space-y-2 mb-6">
          {repExercises.map(ex => (
            <div key={ex.id} className="flex items-center justify-between text-sm">
              <span className="text-neutral-400">{ex.name}</span>
              <span className="font-mono text-neutral-200">{repCounts[ex.id] || 0} reps</span>
            </div>
          ))}
          <div className="flex items-center justify-between text-sm">
            <span className="text-neutral-400">Plank Hold</span>
            <span className="font-mono text-neutral-200">{Math.round(plankHoldSeconds)}s</span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-white/10 mb-6">
          <span className="text-[11px] font-semibold text-neutral-500 uppercase tracking-[0.15em]">Total Reps</span>
          <span className="text-xl font-semibold text-white">{totalReps}</span>
        </div>

        <button
          onClick={onGenerateReport}
          disabled={reportStatus === 'generating'}
          className="w-full mb-2 py-3 rounded-full font-semibold bg-white text-black hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {reportStatus === 'generating' ? 'Generating Report...' : 'Generate Injury Report'}
        </button>
        {reportStatus === 'error' && (
          <p className="text-red-400 text-xs text-center mb-4">{reportError}</p>
        )}

        <div className="flex flex-col gap-2">
          <button
            onClick={onDismiss}
            className="w-full py-3 rounded-full font-semibold border border-white/15 text-white hover:bg-white/5 transition-colors"
          >
            Start New Workout
          </button>
          <button
            onClick={onBackToDashboard}
            className="w-full py-3 rounded-full font-medium bg-transparent text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

export default SummaryScreen;
