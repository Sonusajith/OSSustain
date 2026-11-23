import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { LoginPage } from './LoginPage'
import { PasswordChangePage } from './PasswordChangePage'
import { server } from '../../test/server'

function renderAuth(path = '/login') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/password" element={<PasswordChangePage />} />
          <Route path="/analyze" element={<h1>Analyze page</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('account pages', () => {
  it('signs in, requires a password change, and then continues', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('http://localhost:8080/api/v1/auth/login', ({ request }) => {
        expect(request.headers.get('X-CSRF-TOKEN')).toBe('test-csrf-token')
        return HttpResponse.json({ id: 1, username: 'researcher', roles: ['RESEARCHER'], mustChangePassword: true })
      }),
      http.post('http://localhost:8080/api/v1/auth/password', ({ request }) => {
        expect(request.headers.get('X-CSRF-TOKEN')).toBe('test-csrf-token')
        return HttpResponse.json({ id: 1, username: 'researcher', roles: ['RESEARCHER'], mustChangePassword: false })
      }),
    )
    renderAuth()

    await user.type(screen.getByLabelText('Username'), 'researcher')
    await user.type(screen.getByLabelText('Password'), 'temporary-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Temporary or current password'), 'temporary-password')
    await user.type(screen.getByLabelText('New password'), 'a-strong-new-password-2026')
    await user.type(screen.getByLabelText('Confirm new password'), 'a-strong-new-password-2026')
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByRole('heading', { name: 'Analyze page' })).toBeInTheDocument()
  })

  it('shows a credential error without exposing account details', async () => {
    server.use(http.post('http://localhost:8080/api/v1/auth/login', () => HttpResponse.json(
      { timestamp: new Date().toISOString(), status: 401, code: 'invalid_credentials', message: 'The username or password is incorrect.', path: '/api/v1/auth/login' },
      { status: 401 },
    )))
    renderAuth()
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'unknown' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('username or password is incorrect')
  })
})
