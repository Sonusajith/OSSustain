import { Link, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useCurrentUser, useLogout } from './api/queries'

import { CohortOverview } from './features/cohort/CohortOverview'
import { RepositoryComparisonPage } from './features/comparison/RepositoryComparisonPage'
import { MethodologyPage } from './features/research/MethodologyPage'
import { ResearchResultsPage } from './features/research/ResearchResultsPage'
import { RepositoryDetailPage } from './features/repository/RepositoryDetailPage'
import { AnalysisPage } from './features/analysis/AnalysisPage'
import { LoginPage } from './features/auth/LoginPage'
import { PasswordChangePage } from './features/auth/PasswordChangePage'
import { AdminPage } from './features/admin/AdminPage'

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

function RequireAccount({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const user = useCurrentUser()
  const location = useLocation()
  if (user.isPending) return <main className="auth-page" role="status">Checking your sign-in…</main>
  if (user.isError) return <main className="auth-page" role="alert">{user.error.message}</main>
  if (!user.data) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.data.mustChangePassword && location.pathname !== '/password') return <Navigate to="/password" replace />
  if (admin && !user.data.roles.includes('ADMIN')) {
    return <main className="auth-page"><h1>Administrator access required</h1><p>Your account cannot open this page.</p><Link className="text-link" to="/">Return to public research</Link></main>
  }
  return <>{children}</>
}

export function App() {
  const currentUser = useCurrentUser()
  const logout = useLogout()
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
            <NavLink to="/compare">Compare</NavLink>
            <NavLink to="/analyze">Analyze repository</NavLink>
            {currentUser.data?.roles.includes('ADMIN') && <NavLink to="/admin">Admin</NavLink>}
          </nav>
          <div className="account-actions">
            {currentUser.data ? <><span>{currentUser.data.username}</span><button className="secondary-button" type="button" onClick={() => logout.mutate()}>Sign out</button></>
              : <Link className="source-link" to="/login">Sign in</Link>}
          </div>
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
        <Route path="/compare" element={<RepositoryComparisonPage />} />
        <Route path="/analyze" element={<RequireAccount><AnalysisPage /></RequireAccount>} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/password" element={<RequireAccount><PasswordChangePage /></RequireAccount>} />
        <Route path="/admin" element={<RequireAccount admin><AdminPage /></RequireAccount>} />
        <Route path="*" element={<PlaceholderPage title="Page not found" description="This route is not part of the current dashboard." />} />
      </Routes>
      <footer className="site-footer">
        <span>OSSustain · empirical research on contribution activity</span>
        <span>Predictions describe activity decline only; they do not claim causation.</span>
      </footer>
    </div>
  )
}
