import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('application foundation shell', () => {
  it('renders the navigation and foundation placeholder', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'OSSustain foundation' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Research' })).toHaveAttribute('href', '/research')
  })

  it('renders the placeholder at a nested repository route', () => {
    render(
      <MemoryRouter initialEntries={['/repositories/123']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByText('Current route: /repositories/123')).toBeInTheDocument()
  })
})
