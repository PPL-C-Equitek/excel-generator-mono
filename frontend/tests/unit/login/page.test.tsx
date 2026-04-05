import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Page from '../../../src/app/login/page'

describe('login/page', () => {
    it('renders without crashing', () => {
        const { container } = render(<Page />)
        expect(container).toBeTruthy()
    })
})