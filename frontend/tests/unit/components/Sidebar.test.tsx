import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import * as auth from '@/lib/auth'
import Sidebar from '../../../src/components/Sidebar'

describe('Sidebar', () => {
    it('renders brand name EQUITEK', () => {
        render(<Sidebar activeMenu="convert" username="John" />)
        expect(screen.getByText('EQUITEK')).toBeInTheDocument()
    })

    it('renders Convert, Schema, and History menu', () => {
        render(<Sidebar activeMenu="convert" username="John" />)
        expect(screen.getByText('Convert')).toBeInTheDocument()
        expect(screen.getByText('Schema')).toBeInTheDocument()
        expect(screen.getByText('History')).toBeInTheDocument()
    })

    it('marks Convert as active when activeMenu is convert', () => {
        render(<Sidebar activeMenu="convert" username="John" />)
        expect(screen.getByText('Convert').closest('a')).toHaveClass('bg-white')
    })

    it('marks Schema as active when activeMenu is schema', () => {
        render(<Sidebar activeMenu="schema" username="John" />)
        expect(screen.getByText('Schema').closest('a')).toHaveClass('bg-white')
    })

    it('renders username at the bottom', () => {
        vi.spyOn(auth, 'getStoredUser').mockReturnValue({
            id: 1,
            email: 'john@example.com',
            name: 'JohnDoe',
        })

        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('JohnDoe')).toBeInTheDocument()
    })
})
