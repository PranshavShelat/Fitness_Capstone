import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// No StrictMode: it double-invokes effects in dev, and MediaPipe's Pose/Camera
// (WASM model + getUserMedia stream) doesn't tolerate being torn down and
// recreated within milliseconds - it leaves onResults never firing again.
createRoot(document.getElementById('root')).render(
  <App />,
)
