import { useState } from 'react'
import type { FormEvent } from 'react'

import { useAdminAnalyses, useAdminUsers, useCancelAdminAnalysis, useCreateAdminUser, useSetAdminUserEnabled } from '../../api/queries'

export function AdminPage() {
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<'ADMIN' | 'RESEARCHER'>('RESEARCHER')
  const [temporaryPassword, setTemporaryPassword] = useState<string>()
  const users = useAdminUsers()
  const analyses = useAdminAnalyses()
  const createUser = useCreateAdminUser()
  const setEnabled = useSetAdminUserEnabled()
  const cancelAnalysis = useCancelAdminAnalysis()

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    createUser.mutate({ username: username.trim(), role }, {
      onSuccess: (created) => {
        setTemporaryPassword(created.temporaryPassword)
        setUsername('')
      },
    })
  }

  return (
    <main className="admin-page">
      <p className="eyebrow">Administration</p>
      <h1>Users and analysis jobs</h1>
      <p className="admin-intro">Manage invite-only accounts and the bounded analysis queue. Temporary passwords appear once and are never stored in readable form.</p>

      <section className="admin-panel" aria-labelledby="create-account-heading">
        <h2 id="create-account-heading">Create an account</h2>
        <form className="admin-create-form" onSubmit={handleCreate}>
          <label htmlFor="new-username">Username</label>
          <input id="new-username" minLength={3} maxLength={100} pattern="[A-Za-z0-9][A-Za-z0-9._-]{2,99}" required value={username} onChange={(event) => setUsername(event.target.value)} />
          <label htmlFor="new-role">Role</label>
          <select id="new-role" value={role} onChange={(event) => setRole(event.target.value as 'ADMIN' | 'RESEARCHER')}>
            <option value="RESEARCHER">Researcher</option>
            <option value="ADMIN">Administrator</option>
          </select>
          <button className="primary-button" type="submit" disabled={createUser.isPending}>{createUser.isPending ? 'Creating…' : 'Create account'}</button>
        </form>
        {createUser.isError && <p className="admin-error" role="alert">{createUser.error.message}</p>}
        {temporaryPassword && <div className="temporary-password" role="status"><strong>Copy this temporary password now:</strong><code>{temporaryPassword}</code><p>The new user must change it at first sign-in. This value will not be shown again.</p></div>}
      </section>

      <section className="admin-panel" aria-labelledby="accounts-heading">
        <h2 id="accounts-heading">Accounts</h2>
        {users.isPending ? <p role="status">Loading accounts…</p> : users.isError ? <div role="alert"><p>{users.error.message}</p><button className="secondary-button" onClick={() => void users.refetch()}>Retry accounts</button></div> : users.data?.content.length === 0 ? <p>No accounts have been created.</p> : (
          <div className="admin-table-scroll" role="region" aria-label="Account list" tabIndex={0}>
            <table><thead><tr><th scope="col">Username</th><th scope="col">Roles</th><th scope="col">Status</th><th scope="col">Password</th><th scope="col">Action</th></tr></thead>
              <tbody>{users.data?.content.map((user) => <tr key={user.id}>
                <th scope="row">{user.username}</th><td>{user.roles.join(', ')}</td><td>{user.enabled ? 'Enabled' : 'Disabled'}</td>
                <td>{user.mustChangePassword ? 'Change required' : 'Set'}</td>
                <td><button className="secondary-button" type="button" disabled={setEnabled.isPending} onClick={() => setEnabled.mutate({ id: user.id, enabled: !user.enabled })}>{user.enabled ? 'Disable' : 'Enable'}</button></td>
              </tr>)}</tbody>
            </table>
          </div>
        )}
        {setEnabled.isError && <p className="admin-error" role="alert">{setEnabled.error.message}</p>}
      </section>

      <section className="admin-panel" aria-labelledby="jobs-heading">
        <h2 id="jobs-heading">Recent analysis jobs</h2>
        {analyses.isPending ? <p role="status">Loading analysis jobs…</p> : analyses.isError ? <div role="alert"><p>{analyses.error.message}</p><button className="secondary-button" onClick={() => void analyses.refetch()}>Retry jobs</button></div> : analyses.data?.content.length === 0 ? <p>No recent analysis jobs.</p> : (
          <div className="admin-table-scroll" role="region" aria-label="Analysis queue" tabIndex={0}>
            <table><thead><tr><th scope="col">Repository</th><th scope="col">Submitted by</th><th scope="col">Status</th><th scope="col">Created</th><th scope="col">Action</th></tr></thead>
              <tbody>{analyses.data?.content.map((job) => <tr key={job.id}>
                <th scope="row">{job.repository}</th><td>{job.submittedBy ?? 'Legacy anonymous job'}</td><td>{job.status.replaceAll('_', ' ')}</td><td>{new Date(job.createdAt).toLocaleString()}</td>
                <td>{job.status === 'queued' || job.status === 'running' ? <button className="secondary-button" type="button" disabled={cancelAnalysis.isPending} onClick={() => cancelAnalysis.mutate(job.id)}>Cancel</button> : '—'}</td>
              </tr>)}</tbody>
            </table>
          </div>
        )}
        {cancelAnalysis.isError && <p className="admin-error" role="alert">{cancelAnalysis.error.message}</p>}
      </section>
    </main>
  )
}
