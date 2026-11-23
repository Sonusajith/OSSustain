import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useChangePassword } from '../../api/queries'

export function PasswordChangePage() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const changePassword = useChangePassword()
  const navigate = useNavigate()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (newPassword !== confirmation) return
    changePassword.mutate({ currentPassword, newPassword }, { onSuccess: () => navigate('/analyze', { replace: true }) })
  }

  return (
    <main className="auth-page">
      <p className="eyebrow">Account security</p>
      <h1>Choose a new password</h1>
      <p className="auth-intro">Your administrator issued a one-time password. Set a private password before continuing.</p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="current-password">Temporary or current password</label>
        <input id="current-password" type="password" autoComplete="current-password" minLength={1} maxLength={200} required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
        <label htmlFor="new-password">New password</label>
        <input id="new-password" type="password" autoComplete="new-password" minLength={16} maxLength={200} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
        <label htmlFor="confirm-password">Confirm new password</label>
        <input id="confirm-password" type="password" autoComplete="new-password" minLength={16} maxLength={200} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
        {confirmation && newPassword !== confirmation && <p className="auth-error" role="alert">The new passwords do not match.</p>}
        {changePassword.isError && <p className="auth-error" role="alert">{changePassword.error.message}</p>}
        <button className="primary-button" type="submit" disabled={changePassword.isPending || newPassword !== confirmation}>{changePassword.isPending ? 'Saving…' : 'Save new password'}</button>
      </form>
    </main>
  )
}
