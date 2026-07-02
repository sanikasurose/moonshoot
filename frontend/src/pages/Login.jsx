import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_BASE } from '../api/client'

export default function Login() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    const res = await fetch(`${API_BASE}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (!res.ok) {
      setError('Invalid password')
      return
    }
    const { token } = await res.json()
    sessionStorage.setItem('jwt', token)
    navigate('/dashboard')
  }

  return (
    <main>
      <h1>Moonshoot</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Password{' '}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
          />
        </label>
        <button type="submit">Log in</button>
      </form>
      {error && <p role="alert">{error}</p>}
    </main>
  )
}
