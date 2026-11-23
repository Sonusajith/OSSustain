import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useLogin } from '../../api/queries'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()
  const destination = (location.state as { from?: string } | null)?.from ?? '/analyze'

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    login.mutate({ username: username.trim(), password }, {
      onSuccess: (user) => navigate(user.mustChangePassword ? '/password' : destination, { replace: true }),
    })
  }

  return (
    <main className="auth-page">
      <p className="eyebrow">OSSustain account</p>
      <h1>Sign in</h1>
      <p className="auth-intro">Research pages remain public. Sign in to submit and view repository analyses.</p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="login-username">Username</label>
        <input id="login-username" autoComplete="username" required maxLength={100} value={username} onChange={(event) => setUsername(event.target.value)} />
        <label htmlFor="login-password">Password</label>
        <input id="login-password" type="password" autoComplete="current-password" required maxLength={200} value={password} onChange={(event) => setPassword(event.target.value)} />
        {login.isError && <p className="auth-error" role="alert">{login.error.message}</p>}
        <button className="primary-button" type="submit" disabled={login.isPending}>{login.isPending ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <Link className="text-link" to="/">Return to public research</Link>
    </main>
  )
}
