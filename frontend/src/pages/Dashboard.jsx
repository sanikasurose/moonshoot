import { Link } from 'react-router-dom'

export default function Dashboard() {
  return (
    <main>
      <h1>Dashboard</h1>
      <nav>
        <Link to="/resumes">Resumes</Link>
      </nav>
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Title</th>
            <th>City</th>
            <th>Score</th>
            <th>Status</th>
            <th>Date Applied</th>
            <th>Resume</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={7}>No jobs yet</td>
          </tr>
        </tbody>
      </table>
    </main>
  )
}
