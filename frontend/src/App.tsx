import { Link, NavLink, Route, Routes } from 'react-router-dom'

import { CohortOverview } from './features/cohort/CohortOverview'
import { MethodologyPage } from './features/research/MethodologyPage'
import { ResearchResultsPage } from './features/research/ResearchResultsPage'
import { RepositoryDetailPage } from './features/repository/RepositoryDetailPage'

function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <main className="placeholder-page">
      <p className="eyebrow">OSSustain research platform</p>
      <h1>{title}</h1>
      <p>{description}</p>
      <Link className="text-link" to="/">Return to the cohort overview</Link>
    </main>
  )
}

export function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="header-inner">
          <div className="brand-group">
            <Link className="wordmark" to="/" aria-label="OSSustain home">OSSustain</Link>
            <span className="release-badge">Research MVP</span>
          </div>
          <nav aria-label="Main navigation">
            <NavLink end to="/">Cohort Overview</NavLink>
            <NavLink to="/research">Research Results</NavLink>
            <NavLink to="/methodology">Methodology &amp; Limitations</NavLink>
          </nav>
          <a className="source-link" href="https://github.com/Sonusajith/OSSustain" aria-label="OSSustain source repository">
            <span aria-hidden="true">↗</span>
            <span className="source-label">Source</span>
          </a>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<CohortOverview />} />
        <Route
          path="/repositories/:repositoryId"
          element={<RepositoryDetailPage />}
        />
        <Route
          path="/research"
          element={<ResearchResultsPage />}
        />
        <Route
          path="/methodology"
          element={<MethodologyPage />}
        />
        <Route path="*" element={<PlaceholderPage title="Page not found" description="This route is not part of the current dashboard." />} />
      </Routes>
      <footer className="site-footer">
        <span>OSSustain · empirical research on contribution activity</span>
        <span>Predictions describe activity decline only; they do not claim causation.</span>
      </footer>
    </div>
  )
}
