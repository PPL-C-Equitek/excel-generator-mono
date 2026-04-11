import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import * as auth from '@/lib/auth'
import Sidebar from '../../../src/components/Sidebar'

vi.mock('@/components/LogoutButton', () => ({
    default: () => <button type="button">Logout</button>,
}))

describe('Sidebar', () => {
    it('renders brand name EQUITEK', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('EQUITEK')).toBeInTheDocument()
    })

    it('brand name links to home', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('EQUITEK')).toHaveAttribute('href', '/')
    })

    it('renders Convert, Schema, History, and Change Password menu', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('Convert')).toBeInTheDocument()
        expect(screen.getByText('Schema')).toBeInTheDocument()
        expect(screen.getByText('History')).toBeInTheDocument()
        expect(screen.getByText('Change Password')).toBeInTheDocument()
    })

    it('marks Convert as active when activeMenu is convert', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('Convert').closest('a')).toHaveClass('bg-white')
    })

    it('marks Schema as active when activeMenu is schema', () => {
        render(<Sidebar activeMenu="schema" />)
        expect(screen.getByText('Schema').closest('a')).toHaveClass('bg-white')
    })

    it('marks Change Password as active when activeMenu is change-password', () => {
        render(<Sidebar activeMenu="change-password" />)
        expect(screen.getByText('Change Password').closest('a')).toHaveClass('bg-white')
    })

    it('renders stored user name at the bottom', () => {
        vi.spyOn(auth, 'getStoredUser').mockReturnValue({
            id: 1,
            email: 'john@example.com',
            name: 'JohnDoe',
        })

        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('JohnDoe')).toBeInTheDocument()
    })

    it('renders logout button when onLogout is not provided', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
    })

    it('calls onLogout when custom logout button is clicked', () => {
        const onLogout = vi.fn()

        render(<Sidebar activeMenu="convert" onLogout={onLogout} />)
        fireEvent.click(screen.getByRole('button', { name: /logout/i }))

        expect(onLogout).toHaveBeenCalledTimes(1)
    })
})
