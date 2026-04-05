import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Page from '../../../src/app/login/page'

vi.mock('@react-oauth/google', () => ({
    useGoogleLogin: vi.fn(() => vi.fn()),
}))

describe('login/page', () => {
    it('renders without crashing', () => {
        const { container } = render(<Page />)
        expect(container).toBeTruthy()
    })
})