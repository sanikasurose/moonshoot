import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Resumes from './pages/Resumes'

function RequireAuth({ children }) {
  return sessionStorage.getItem('jwt') ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/resumes" element={<RequireAuth><Resumes /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  )
}
