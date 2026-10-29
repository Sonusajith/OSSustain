import { Link, Route, Routes, useLocation } from 'react-router-dom'

const routes = [
  { label: 'Cohort', path: '/' },
  { label: 'Research', path: '/research' },
  { label: 'Methodology', path: '/methodology' },
]

function FoundationRoute() {
  const location = useLocation()

  return (
    <main>
      <h1>OSSustain foundation</h1>
      <p>The application shell is ready. Product screens are added in their planned phases.</p>
      <p className="route-path">Current route: {location.pathname}</p>
    </main>
  )
}

export function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="wordmark" to="/" aria-label="OSSustain home">
          OSSustain
        </Link>
        <nav aria-label="Main navigation">
          {routes.map((route) => (
            <Link key={route.path} to={route.path}>
              {route.label}
            </Link>
          ))}
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<FoundationRoute />} />
        <Route path="/repositories/:repositoryId" element={<FoundationRoute />} />
        <Route path="/research" element={<FoundationRoute />} />
        <Route path="/methodology" element={<FoundationRoute />} />
        <Route path="*" element={<FoundationRoute />} />
      </Routes>
    </div>
  )
}
