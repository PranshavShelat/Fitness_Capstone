import React from 'react';

function formatDuration(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function SummaryScreen({ repCounts, plankHoldSeconds, elapsedSeconds, exercises, repBasedModes, onDismiss, onBackToDashboard, onGenerateReport, reportStatus, reportError }) {
  // Only the exercises actually done this session - listing every exercise with
  // "0 reps" buried the ones that mattered.
  const repExercises = exercises.filter(ex => repBasedModes.has(ex.id) && (repCounts[ex.id] || 0) > 0);
  const plankDone = Math.round(plankHoldSeconds) > 0;
  const totalReps = Object.values(repCounts).reduce((sum, n) => sum + n, 0);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 backdrop-blur-md p-4 sm:p-6">
      <div role="dialog" aria-modal="true" aria-labelledby="summary-title"
           className="w-full max-w-md bg-surface rounded-[32px] shadow-2xl overflow-hidden">
        {/* Header band */}
        <div className="bg-primary text-white px-8 pt-8 pb-7">
          <h2 id="summary-title" className="text-lg font-medium text-white/85">Workout complete. Nice work!</h2>
          <div className="flex items-end gap-8 mt-3">
            <div>
              <p className="text-5xl font-semibold tabular-nums leading-none">{formatDuration(elapsedSeconds)}</p>
              <p className="text-sm text-white/75 mt-1.5">time</p>
            </div>
            <div>
              <p className="text-5xl font-semibold tabular-nums leading-none text-sun">{totalReps}</p>
              <p className="text-sm text-white/75 mt-1.5">total reps</p>
            </div>
          </div>
        </div>

        <div className="px-8 py-6">
          <ul className="divide-y divide-line mb-6">
            {repExercises.map(ex => (
              <li key={ex.id} className="flex items-center justify-between py-2.5 text-[15px]">
                <span className="text-ink">{ex.name}</span>
                <span className="font-semibold tabular-nums text-ink">{repCounts[ex.id]} {repCounts[ex.id] === 1 ? 'rep' : 'reps'}</span>
              </li>
            ))}
            {plankDone && (
              <li className="flex items-center justify-between py-2.5 text-[15px]">
                <span className="text-ink">Plank hold</span>
                <span className="font-semibold tabular-nums text-ink">{Math.round(plankHoldSeconds)} sec</span>
              </li>
            )}
            {repExercises.length === 0 && !plankDone && (
              <li className="py-2.5 text-sm text-muted">No reps were tracked in this workout.</li>
            )}
          </ul>

          <button
            onClick={onGenerateReport}
            disabled={reportStatus === 'generating'}
            className="w-full py-3.5 rounded-full font-semibold bg-sun hover:bg-sun-deep text-ink disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {reportStatus === 'generating' ? 'Writing your report...' : 'Get my form report'}
          </button>
          <p className="text-xs text-muted text-center mt-2">
            {reportStatus === 'generating'
              ? 'This takes about 20 seconds. The PDF downloads when it is ready.'
              : 'A PDF of what went well and what to fix, with videos to watch.'}
          </p>
          {reportStatus === 'error' && (
            <p className="text-bad text-sm text-center mt-2">{reportError}</p>
          )}

          <div className="grid grid-cols-2 gap-2 mt-5">
            <button
              onClick={onDismiss}
              className="py-3 rounded-full font-semibold bg-primary-soft text-primary hover:bg-primary hover:text-white transition-colors"
            >
              New workout
            </button>
            <button
              onClick={onBackToDashboard}
              className="py-3 rounded-full font-semibold text-muted hover:text-ink hover:bg-tint transition-colors"
            >
              Back to dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SummaryScreen;
