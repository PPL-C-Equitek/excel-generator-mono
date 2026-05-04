import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import * as auth from '@/lib/auth'
import Sidebar from '../../../src/components/Sidebar'
import { useHistoryFiles } from '@/hooks/useHistoryFiles'
import { getMonitoringAccess } from '@/services/monitoring'

vi.mock('@/hooks/useHistoryFiles', () => ({
    useHistoryFiles: vi.fn(),
}))

vi.mock('@/components/LogoutButton', () => ({
    default: () => <button type="button">Logout</button>,
}))

vi.mock('@/components/HistorySidebarList', () => ({
    default: () => <div data-testid="history-sidebar-list">History Sidebar List</div>,
}))

vi.mock('@/services/monitoring', () => ({
    getMonitoringAccess: vi.fn(),
}))

const mockUseHistoryFiles = vi.mocked(useHistoryFiles)
const mockGetMonitoringAccess = vi.mocked(getMonitoringAccess)

function makeHistoryHookState() {
    return {
        items: [],
        count: 0,
        limit: 50,
        offset: 0,
        isLoading: false,
        renamingHistoryId: null,
        deletingHistoryId: null,
        isDownloading: vi.fn().mockReturnValue(false),
        downloadError: null,
        loadError: null,
        mutationError: null,
        error: null,
        reloadHistory: vi.fn().mockResolvedValue(undefined),
        goToNextPage: vi.fn().mockResolvedValue(undefined),
        goToPreviousPage: vi.fn().mockResolvedValue(undefined),
        downloadCsv: vi.fn().mockResolvedValue(undefined),
        downloadExcel: vi.fn().mockResolvedValue(undefined),
        renameHistory: vi.fn().mockResolvedValue(true),
        deleteHistory: vi.fn().mockResolvedValue(true),
    }
}

describe('Sidebar', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseHistoryFiles.mockReturnValue(makeHistoryHookState())
        mockGetMonitoringAccess.mockResolvedValue({
            allowed: false,
            reason: 'no_account',
        })
    })

    it('renders brand name EQUITEK', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('EQUITEK')).toBeInTheDocument()
    })

    it('brand name links to home', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('EQUITEK')).toHaveAttribute('href', '/')
    })

    it('renders non-monitoring menus by default', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByText('Convert')).toBeInTheDocument()
        expect(screen.getByText('Schema')).toBeInTheDocument()
        expect(screen.getByText('Change Password')).toBeInTheDocument()
        expect(screen.queryByText('Monitoring')).not.toBeInTheDocument()
    })

    it('renders Monitoring menu when the user has monitoring access', async () => {
        mockGetMonitoringAccess.mockResolvedValue({
            allowed: true,
            reason: 'ok',
        })

        render(<Sidebar activeMenu="convert" />)

        await waitFor(() => {
            expect(screen.getByText('Monitoring')).toBeInTheDocument()
        })
    })

    it('does not render History as a separate top menu label', () => {
        render(<Sidebar activeMenu="history" />)
        expect(screen.queryByRole('link', { name: 'History' })).not.toBeInTheDocument()
    })

    it('renders the history sidebar list block', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByTestId('history-sidebar-list')).toBeInTheDocument()
    })

    it('keeps sidebar modal backdrops above convert page overlays', () => {
        render(<Sidebar activeMenu="convert" />)
        expect(screen.getByRole('complementary')).toHaveClass('z-50')
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

    it('marks Monitoring as active when activeMenu is monitoring and access is allowed', async () => {
        mockGetMonitoringAccess.mockResolvedValue({
            allowed: true,
            reason: 'ok',
        })

        render(<Sidebar activeMenu="monitoring" />)

        await waitFor(() => {
            expect(screen.getByText('Monitoring').closest('a')).toHaveClass('bg-white')
        })
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
