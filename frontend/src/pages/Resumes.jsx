import { Link } from 'react-router-dom'

export default function Resumes() {
  return (
    <main>
      <h1>Resumes</h1>
      <nav>
        <Link to="/dashboard">Dashboard</Link>
      </nav>
      <p>No resumes yet</p>
    </main>
  )
}
