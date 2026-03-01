import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Sidebar from '../../../src/components/Sidebar'

describe('Sidebar', () => {
    it('renders brand name EQUITEK', () => {
        render(<Sidebar activeMenu="convert" username="John" />)
        expect(screen.getByText('EQUITEK')).toBeInTheDocument()
    })

    it('renders Convert and History menu', () => {
        render(<Sidebar activeMenu="convert" username="John" />)
        expect(screen.getByText('Convert')).toBeInTheDocument()
        expect(screen.getByText('History')).toBeInTheDocument()
    })

    it('marks Convert as active when activeMenu is convert', () => {
        render(<Sidebar activeMenu="convert" username="John" />)
        expect(screen.getByText('Convert').closest('a')).toHaveClass('bg-white')
    })

    it('renders username at the bottom', () => {
        render(<Sidebar activeMenu="convert" username="JohnDoe" />)
        expect(screen.getByText('JohnDoe')).toBeInTheDocument()
    })
})