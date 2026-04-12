import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import HistoryPage from '../../../src/app/history/HistoryPage'
import { useHistoryFiles } from '../../../src/hooks/useHistoryFiles'

vi.mock('../../../src/hooks/useHistoryFiles', () => ({
    useHistoryFiles: vi.fn(),
}))

vi.mock('../../../src/components/Sidebar', () => ({
    default: ({ activeMenu }: { activeMenu: string }) => (
        <div data-testid="sidebar">
            <div data-testid="active-menu">{activeMenu}</div>
        </div>
    ),
}))

const mockUseHistoryFiles = vi.mocked(useHistoryFiles)

const historyItems = [
    {
        id: '11111111-1111-1111-1111-111111111111',
        original_name: 'report-a.pdf',
        custom_name: '',
        status_processing: 'completed',
        created_at: '2026-04-10T10:00:00Z',
    },
    {
        id: '22222222-2222-2222-2222-222222222222',
        original_name: 'report-b.pdf',
        custom_name: 'Budget Sheet',
        status_processing: 'completed',
        created_at: '2026-04-09T10:00:00Z',
    },
]

function makeHookState(overrides?: Partial<ReturnType<typeof useHistoryFiles>>) {
    return {
        items: historyItems,
        count: 25,
        limit: 10,
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
        ...overrides,
    }
}

describe('HistoryPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseHistoryFiles.mockReturnValue(makeHookState())
    })

    it('renders the history title and sidebar state', () => {
        render(<HistoryPage />)

        expect(screen.getByText('History')).toBeInTheDocument()
        expect(screen.getByTestId('active-menu')).toHaveTextContent('history')
    })

    it('renders history items with download actions', () => {
        render(<HistoryPage />)

        expect(screen.getByText('report-a.pdf')).toBeInTheDocument()
        expect(screen.getByText('Budget Sheet')).toBeInTheDocument()
        expect(screen.getAllByRole('button', { name: 'Edit Name' })).toHaveLength(2)
        expect(screen.getAllByRole('button', { name: 'Delete' })).toHaveLength(2)
        expect(screen.getAllByRole('button', { name: 'Download CSV' })).toHaveLength(2)
        expect(screen.getAllByRole('button', { name: 'Download Excel' })).toHaveLength(2)
    })

    it('formats created_at into a readable UTC timestamp', () => {
        render(<HistoryPage />)

        expect(screen.getByText('Created at: 10 Apr 2026, 17:00 UTC+7')).toBeInTheDocument()
        expect(screen.getByText('Created at: 09 Apr 2026, 17:00 UTC+7')).toBeInTheDocument()
    })

    it('falls back to the original name when custom_name is empty', () => {
        render(<HistoryPage />)

        expect(screen.getAllByText('report-a.pdf')).not.toHaveLength(0)
    })

    it('renders loading state while history is loading', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                isLoading: true,
                items: [],
                count: 0,
            })
        )

        render(<HistoryPage />)

        expect(screen.getByText('Loading history...')).toBeInTheDocument()
    })

    it('renders an empty state when the history list is empty', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [],
                count: 0,
            })
        )

        render(<HistoryPage />)

        expect(screen.getByText('No history yet')).toBeInTheDocument()
    })

    it('renders an error state and allows retry', () => {
        const reloadHistory = vi.fn().mockResolvedValue(undefined)
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [],
                count: 0,
                loadError: 'Failed to load history.',
                error: 'Failed to load history.',
                reloadHistory,
            })
        )

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

        expect(screen.getByText('Failed to load history.')).toBeInTheDocument()
        expect(reloadHistory).toHaveBeenCalledTimes(1)
    })

    it('renders a download error banner when a download fails', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                downloadError: 'Failed to download history file.',
                error: 'Failed to download history file.',
            })
        )

        render(<HistoryPage />)

        expect(
            screen.getByText('Failed to download history file.')
        ).toBeInTheDocument()
    })

    it('renders a mutation error banner when rename or delete fails', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                mutationError: 'Failed to rename history item.',
                error: 'Failed to rename history item.',
            })
        )

        render(<HistoryPage />)

        expect(
            screen.getByText('Failed to rename history item.')
        ).toBeInTheDocument()
    })

    it('calls the csv download action for an item', () => {
        const downloadCsv = vi.fn().mockResolvedValue(undefined)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ downloadCsv }))

        render(<HistoryPage />)

        const csvButton = screen.getAllByRole('button', { name: 'Download CSV' })[0]
        expect(csvButton).toHaveClass('hover:bg-red-800')
        fireEvent.click(csvButton)

        expect(downloadCsv).toHaveBeenCalledWith(
            historyItems[0].id,
            'report-a.csv'
        )
    })

    it('calls the excel download action for an item', () => {
        const downloadExcel = vi.fn().mockResolvedValue(undefined)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ downloadExcel }))

        render(<HistoryPage />)

        const excelButton = screen.getAllByRole('button', { name: 'Download Excel' })[1]
        expect(excelButton).toHaveClass('hover:bg-red-50')
        fireEvent.click(excelButton)

        expect(downloadExcel).toHaveBeenCalledWith(
            historyItems[1].id,
            'report-b.xlsx'
        )
    })

    it('disables and relabels the csv button while the matching item is downloading', () => {
        const isDownloading = vi.fn().mockImplementation((historyId: string, fileFormat: 'csv' | 'xlsx') => {
            return historyId === historyItems[0].id && fileFormat === 'csv'
        })
        mockUseHistoryFiles.mockReturnValue(makeHookState({ isDownloading }))

        render(<HistoryPage />)

        const csvButton = screen.getByRole('button', { name: 'Downloading CSV...' })
        expect(csvButton).toBeDisabled()
    })

    it('disables and relabels the excel button while the matching item is downloading', () => {
        const isDownloading = vi.fn().mockImplementation((historyId: string, fileFormat: 'csv' | 'xlsx') => {
            return historyId === historyItems[1].id && fileFormat === 'xlsx'
        })
        mockUseHistoryFiles.mockReturnValue(makeHookState({ isDownloading }))

        render(<HistoryPage />)

        const excelButton = screen.getByRole('button', { name: 'Downloading Excel...' })
        expect(excelButton).toBeDisabled()
    })

    it('opens inline rename mode and submits a renamed display name', async () => {
        const renameHistory = vi.fn().mockResolvedValue(true)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ renameHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getAllByRole('button', { name: 'Edit Name' })[0])
        fireEvent.change(screen.getByLabelText('Display Name'), {
            target: { value: 'Quarterly Report' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'Save Name' }))

        await waitFor(() => {
            expect(renameHistory).toHaveBeenCalledWith(
                historyItems[0].id,
                'Quarterly Report'
            )
        })
    })

    it('allows inline rename mode to be cancelled', () => {
        render(<HistoryPage />)

        fireEvent.click(screen.getAllByRole('button', { name: 'Edit Name' })[0])
        expect(screen.getByLabelText('Display Name')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

        expect(screen.queryByLabelText('Display Name')).not.toBeInTheDocument()
    })

    it('opens the delete dialog and confirms item deletion', async () => {
        const deleteHistory = vi.fn().mockResolvedValue(true)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ deleteHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getAllByRole('button', { name: 'Delete' })[0])
        expect(screen.getByRole('dialog')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Delete History' }))

        await waitFor(() => {
            expect(deleteHistory).toHaveBeenCalledWith(historyItems[0].id)
        })
    })

    it('closes the delete dialog without deleting when cancelled', () => {
        const deleteHistory = vi.fn().mockResolvedValue(true)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ deleteHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getAllByRole('button', { name: 'Delete' })[0])
        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
        expect(deleteHistory).not.toHaveBeenCalled()
    })

    it('uses default download filenames when the original name has no extension', () => {
        const downloadCsv = vi.fn().mockResolvedValue(undefined)
        const downloadExcel = vi.fn().mockResolvedValue(undefined)
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [
                    {
                        id: '33333333-3333-3333-3333-333333333333',
                        original_name: 'report',
                        custom_name: '',
                        status_processing: 'completed',
                        created_at: '2026-04-08T10:00:00Z',
                    },
                ],
                count: 1,
                downloadCsv,
                downloadExcel,
            })
        )

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }))
        fireEvent.click(screen.getByRole('button', { name: 'Download Excel' }))

        expect(downloadCsv).toHaveBeenCalledWith(
            '33333333-3333-3333-3333-333333333333',
            'report.csv'
        )
        expect(downloadExcel).toHaveBeenCalledWith(
            '33333333-3333-3333-3333-333333333333',
            'report.xlsx'
        )
    })

    it('falls back to the raw created_at value when the timestamp is invalid', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [
                    {
                        id: '44444444-4444-4444-4444-444444444444',
                        original_name: 'broken-date.pdf',
                        custom_name: '',
                        status_processing: 'completed',
                        created_at: 'not-a-date',
                    },
                ],
                count: 1,
            })
        )

        render(<HistoryPage />)

        expect(screen.getByText('Created at: not-a-date')).toBeInTheDocument()
    })

    it('shows pagination controls when more history items are available', () => {
        render(<HistoryPage />)

        expect(screen.getByRole('button', { name: 'Previous' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Next' })).toHaveClass('hover:bg-gray-100')
    })

    it('disables previous pagination on the first page', () => {
        render(<HistoryPage />)

        expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    })

    it('calls the next page action from pagination', () => {
        const goToNextPage = vi.fn().mockResolvedValue(undefined)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ goToNextPage }))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Next' }))

        expect(goToNextPage).toHaveBeenCalledTimes(1)
    })

    it('calls the previous page action when pagination is enabled', () => {
        const goToPreviousPage = vi.fn().mockResolvedValue(undefined)
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                count: 25,
                offset: 10,
                goToPreviousPage,
            })
        )

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Previous' }))

        expect(goToPreviousPage).toHaveBeenCalledTimes(1)
    })
})
