import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import { AppShell } from './components/AppShell'
import { FlowDraftProvider } from './lib/flowDraft'
import { LibraryScreen } from './screens/LibraryScreen'
import { PersonasScreen } from './screens/PersonasScreen'
import { ProfileScreen } from './screens/ProfileScreen'
import { SimulationScreen } from './screens/SimulationScreen'
import { StartScreen } from './screens/StartScreen'

function App() {
  return (
    <FlowDraftProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/start" replace />} />
            <Route path="/start" element={<StartScreen />} />
            <Route path="/personas" element={<PersonasScreen />} />
            <Route path="/simulation/:sessionId" element={<SimulationScreen />} />
            <Route path="/simulation" element={<Navigate to="/personas" replace />} />
            <Route path="/library" element={<LibraryScreen />} />
            <Route path="/profile" element={<ProfileScreen />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </FlowDraftProvider>
  )
}

export default App

