import type { ReactNode } from 'react'

export function ResearchLoading({ label }: { label: string }) {
  return <main className="research-page" aria-busy="true" aria-live="polite"><div className="research-state" role="status">Loading {label}…</div></main>
}

export function ResearchFailure({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="research-page">
      <section className="research-state research-error" role="alert">
        <h1>Research data could not be loaded</h1>
        <p>{message}</p>
        <button className="detail-button" type="button" onClick={onRetry}>Try again</button>
      </section>
    </main>
  )
}

export function ResearchEmpty({ children }: { children: ReactNode }) {
  return <div className="research-state" role="status">{children}</div>
}
