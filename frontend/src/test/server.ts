import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

export const server = setupServer(
  http.get('http://localhost:8080/api/v1/auth/me', () => HttpResponse.json(
    { timestamp: new Date().toISOString(), status: 401, code: 'authentication_required', message: 'Sign in to access this resource.', path: '/api/v1/auth/me' },
    { status: 401 },
  )),
  http.get('http://localhost:8080/api/v1/auth/csrf', () => HttpResponse.json({
    headerName: 'X-CSRF-TOKEN', parameterName: '_csrf', token: 'test-csrf-token',
  })),
  http.get('http://localhost:8080/api/v1/admin/analyses', () => HttpResponse.json({
    content: [], page: 0, pageSize: 100, totalElements: 0,
  })),
)
