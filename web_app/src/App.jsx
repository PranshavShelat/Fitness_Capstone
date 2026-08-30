import { useState } from 'react';
import Dashboard from './Dashboard';
import WorkoutView from './WorkoutView';

function App() {
  const [view, setView] = useState('dashboard'); // 'dashboard' | 'workout'

  return view === 'dashboard'
    ? <Dashboard onStartWorkout={() => setView('workout')} />
    : <WorkoutView onExit={() => setView('dashboard')} />;
}

export default App;
