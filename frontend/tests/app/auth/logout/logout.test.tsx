import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import LogoutButton from '@/components/LogoutButton'
import { useRouter } from 'next/navigation'
import { toast } from 'react-hot-toast'

const mockPush = jest.fn()
const mockReplace = jest.fn()

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}))

jest.mock(
  'react-hot-toast',
  () => ({
    toast: {
      success: jest.fn(),
      error: jest.fn(),
    },
  }),
  { virtual: true }
)

function ProtectedRouteProbe() {
  const router = useRouter()

  React.useEffect(() => {
    const hasLocalStorageToken =
      Boolean(window.localStorage.getItem('access_token')) ||
      Boolean(window.localStorage.getItem('accessToken'))

    const hasCookieToken =
      document.cookie.includes('access_token=') ||
      document.cookie.includes('accessToken=')

    if (!hasLocalStorageToken && !hasCookieToken) {
      router.replace('/login')
    }
  }, [router])

  return <div data-testid="protected-page">Protected page</div>
}

describe('LogoutButton', () => {
  beforeEach(() => {
    jest.clearAllMocks()

    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      replace: mockReplace,
      refresh: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
      forward: jest.fn(),
    })

    Object.defineProperty(global, 'fetch', {
      writable: true,
      value: jest.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ detail: 'Logged out successfully' }),
      }),
    })

    window.localStorage.clear()
    window.sessionStorage.clear()

    document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    document.cookie = 'refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
  })

  it('renders the logout button and exposes an accessible name', () => {
    render(<LogoutButton />)

    expect(
      screen.getByRole('button', { name: /logout/i })
    ).toBeInTheDocument()
  })

  it('calls POST /auth/logout/, clears auth state, shows a success toast, and redirects to the homepage', async () => {
    const user = userEvent.setup()

    window.localStorage.setItem('access_token', 'test-access-token')
    window.localStorage.setItem('refresh_token', 'test-refresh-token')
    document.cookie = 'access_token=test-cookie-token; path=/'
    document.cookie = 'refresh_token=test-cookie-refresh; path=/'

    render(<LogoutButton />)

    await user.click(screen.getByRole('button', { name: /logout/i }))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/logout/'),
        expect.objectContaining({
          method: 'POST',
        })
      )
    })

    await waitFor(() => {
      const redirectedHome =
        mockPush.mock.calls.some(([path]) => path === '/') ||
        mockReplace.mock.calls.some(([path]) => path === '/')

      expect(redirectedHome).toBe(true)
    })

    expect(toast.success).toHaveBeenCalled()

    const localStorageCleared =
      window.localStorage.getItem('access_token') === null &&
      window.localStorage.getItem('refresh_token') === null &&
      window.localStorage.getItem('accessToken') === null

    const cookiesCleared =
      !document.cookie.includes('access_token=') &&
      !document.cookie.includes('refresh_token=')

    expect(localStorageCleared || cookiesCleared).toBe(true)
  })

  it('prevents duplicate logout requests when clicked multiple times quickly', async () => {
    const user = userEvent.setup()

    ;(global.fetch as jest.Mock).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => ({ detail: 'Logged out successfully' }),
              }),
            50
          )
        )
    )

    render(<LogoutButton />)

    const logoutButton = screen.getByRole('button', { name: /logout/i })

    await Promise.all([user.click(logoutButton), user.click(logoutButton)])

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1)
    })
  })

  it('redirects to /login on a protected page once logout removes the token', async () => {
    const user = userEvent.setup()

    window.localStorage.setItem('access_token', 'test-access-token')

    const { rerender } = render(
      <>
        <LogoutButton />
        <ProtectedRouteProbe />
      </>
    )

    expect(screen.getByTestId('protected-page')).toBeInTheDocument()
    expect(mockReplace).not.toHaveBeenCalledWith('/login')

    await user.click(screen.getByRole('button', { name: /logout/i }))

    rerender(
      <>
        <LogoutButton />
        <ProtectedRouteProbe />
      </>
    )

    await waitFor(() => {
      const redirectedToLogin =
        mockPush.mock.calls.some(([path]) => path === '/login') ||
        mockReplace.mock.calls.some(([path]) => path === '/login')

      expect(redirectedToLogin).toBe(true)
    })
  })
})
