import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSearchParams } from 'next/navigation'
import HistoryPage from '../../../src/app/history/HistoryPage'
import { useHistoryFiles } from '../../../src/hooks/useHistoryFiles'
import { useSessionResume } from '../../../src/hooks/useSessionResume'
import { useSessionThinkingLogs } from '../../../src/hooks/useSessionThinkingLogs'
import {
    downloadSessionOutputCsvFile,
    downloadSessionOutputExcelFile,
} from '../../../src/services/llm'

vi.mock('../../../src/hooks/useHistoryFiles', () => ({
    useHistoryFiles: vi.fn(),
}))

vi.mock('../../../src/hooks/useSessionResume', () => ({
    useSessionResume: vi.fn(),
}))

vi.mock('../../../src/hooks/useSessionThinkingLogs', () => ({
    useSessionThinkingLogs: vi.fn(),
}))

vi.mock('next/navigation', () => ({
    useSearchParams: vi.fn(),
}))

vi.mock('../../../src/services/llm', () => ({
    downloadSessionOutputCsvFile: vi.fn(),
    downloadSessionOutputExcelFile: vi.fn(),
}))

vi.mock('../../../src/components/Sidebar', () => ({
    default: ({ activeMenu, selectedHistoryId }: { activeMenu: string; selectedHistoryId?: string | null }) => (
        <div data-testid="sidebar">
            <div data-testid="active-menu">{activeMenu}</div>
            <div data-testid="selected-history-id">{selectedHistoryId ?? 'none'}</div>
        </div>
    ),
}))

const mockUseHistoryFiles = vi.mocked(useHistoryFiles)
const mockUseSearchParams = vi.mocked(useSearchParams)
const mockUseSessionResume = vi.mocked(useSessionResume)
const mockUseSessionThinkingLogs = vi.mocked(useSessionThinkingLogs)
const mockDownloadSessionOutputCsvFile = vi.mocked(downloadSessionOutputCsvFile)
const mockDownloadSessionOutputExcelFile = vi.mocked(downloadSessionOutputExcelFile)

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
        original_name: 'report-b',
        custom_name: 'Budget Sheet',
        status_processing: 'completed',
        created_at: 'invalid-date',
    },
]

function makeHookState(overrides?: Partial<ReturnType<typeof useHistoryFiles>>) {
    return {
        items: historyItems,
        count: historyItems.length,
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
        ...overrides,
    }
}

function mockSearchParam(historyId: string | null) {
    mockUseSearchParams.mockReturnValue({
        get: vi.fn().mockImplementation((key: string) => {
            if (key === 'historyId') {
                return historyId
            }

            return null
        }),
    } as never)
}

function mockSessionSearchParam(historyId: string | null, sessionId: string | null) {
    mockUseSearchParams.mockReturnValue({
        get: vi.fn().mockImplementation((key: string) => {
            if (key === 'historyId') {
                return historyId
            }

            if (key === 'sessionId') {
                return sessionId
            }

            return null
        }),
    } as never)
}

function makeSessionResumeState(sessionId: string) {
    return {
        session: {
            id: sessionId,
            title: 'Resume Session',
            created_at: '2026-04-10T10:00:00Z',
            updated_at: '2026-04-10T10:01:00Z',
            last_message_at: null,
            last_output_at: null,
            history: [
                {
                    type: 'output',
                    id: 'output-1',
                    chat_id: null,
                    parent_output_id: null,
                    output_json: { foo: 'bar' },
                    thinking_log: '',
                    reasoning: {},
                    created_at: '2026-04-10T10:01:00Z',
                },
            ],
        },
        isLoading: false,
        error: null,
        isNotFound: false,
    }
}

function makeThinkingLogsState() {
    return {
        thinkingLogsByOutputId: {},
        thinkingLogs: [],
        isLoading: false,
        error: null,
    }
}

describe('HistoryPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSearchParam(null)
        mockUseHistoryFiles.mockReturnValue(makeHookState())
        mockUseSessionResume.mockReturnValue({
            session: null,
            isLoading: false,
            error: null,
            isNotFound: false,
        })
        mockUseSessionThinkingLogs.mockReturnValue(makeThinkingLogsState())
    })

    it('renders sidebar with active history menu and first selected history id', () => {
        render(<HistoryPage />)

        expect(screen.getByTestId('active-menu')).toHaveTextContent('history')
        expect(screen.getByTestId('selected-history-id')).toHaveTextContent(historyItems[0].id)
        expect(mockUseHistoryFiles).toHaveBeenCalledWith({ loadAll: true, pageSize: 50 })
    })

    it('uses historyId query param to select item', () => {
        mockSearchParam(historyItems[1].id)

        render(<HistoryPage />)

        expect(screen.getByTestId('selected-history-id')).toHaveTextContent(historyItems[1].id)
        fireEvent.click(screen.getByRole('button', { name: 'Edit Name' }))
        expect(screen.getByLabelText('File Name')).toHaveValue('Budget Sheet')
    })

    it('uses the sessionId query parameter when present', () => {
        const sessionId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        mockSessionSearchParam(historyItems[1].id, sessionId)
        mockUseSessionResume.mockReturnValue(makeSessionResumeState(sessionId))

        render(<HistoryPage />)

        expect(mockUseSessionResume).toHaveBeenCalledWith(sessionId)
        expect(mockUseSessionThinkingLogs).toHaveBeenCalledWith(sessionId)
        expect(screen.getAllByText('Resume Session').length).toBeGreaterThan(0)
    })

    it('falls back to the selected history session_id when the query parameter is absent', () => {
        const sessionId = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
        mockSearchParam(historyItems[1].id)
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [
                    {
                        ...historyItems[1],
                        session_id: sessionId,
                    },
                ],
            })
        )
        mockUseSessionResume.mockReturnValue(makeSessionResumeState(sessionId))

        render(<HistoryPage />)

        expect(mockUseSessionResume).toHaveBeenCalledWith(sessionId)
        expect(mockUseSessionThinkingLogs).toHaveBeenCalledWith(sessionId)
    })

    it('renders loading state when there is no selected history item', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [],
                count: 0,
                isLoading: true,
            })
        )

        render(<HistoryPage />)

        expect(screen.getByText('Loading history...')).toBeInTheDocument()
    })

    it('renders load error when no selected history item exists', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [],
                count: 0,
                loadError: 'Failed to load history.',
            })
        )

        render(<HistoryPage />)

        expect(screen.getByText('Failed to load history.')).toBeInTheDocument()
    })

    it('renders guidance text when no selected history item and no loading/error state', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [],
                count: 0,
                isLoading: false,
                loadError: null,
            })
        )

        render(<HistoryPage />)

        expect(
            screen.getByText('Choose a history item from the left panel to see details and actions.')
        ).toBeInTheDocument()
    })

    it('renders action error banner when mutation or download fails', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                mutationError: 'Failed to rename history item.',
            })
        )

        render(<HistoryPage />)

        expect(screen.getByText('Failed to rename history item.')).toBeInTheDocument()
    })

    it('formats valid created_at and falls back for invalid created_at', () => {
        mockSearchParam(historyItems[0].id)
        const { unmount } = render(<HistoryPage />)
        expect(screen.getByText('10 Apr 2026, 17:00 UTC+7')).toBeInTheDocument()

        unmount()

        mockSearchParam(historyItems[1].id)
        render(<HistoryPage />)
        expect(screen.getByText('invalid-date')).toBeInTheDocument()
    })

    it('calls latest output download handlers when session output exists', async () => {
        const sessionId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        mockSessionSearchParam(historyItems[0].id, sessionId)
        mockUseSessionResume.mockReturnValue(makeSessionResumeState(sessionId))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Download latest as CSV' }))
        fireEvent.click(screen.getByRole('button', { name: 'Download latest as Excel' }))

        await waitFor(() => {
            expect(mockDownloadSessionOutputCsvFile).toHaveBeenCalledWith(
                sessionId,
                'output-1',
                `session-${sessionId}-latest-output.csv`
            )
            expect(mockDownloadSessionOutputExcelFile).toHaveBeenCalledWith(
                sessionId,
                'output-1',
                `session-${sessionId}-latest-output.xlsx`
            )
        })
    })

    it('allows rename flow and submits new name', async () => {
        const renameHistory = vi.fn().mockResolvedValue(true)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ renameHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Edit Name' }))
        fireEvent.change(screen.getByLabelText('File Name'), {
            target: { value: 'Quarterly Report' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'Save Name' }))

        await waitFor(() => {
            expect(renameHistory).toHaveBeenCalledWith(historyItems[0].id, 'Quarterly Report')
        })
    })

    it('shows rename pending state when save is in progress', () => {
        const { rerender } = render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Edit Name' }))

        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                renamingHistoryId: historyItems[0].id,
            })
        )
        rerender(<HistoryPage />)

        expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled()
    })

    it('keeps rename form open when rename fails', async () => {
        const renameHistory = vi.fn().mockResolvedValue(false)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ renameHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Edit Name' }))
        fireEvent.click(screen.getByRole('button', { name: 'Save Name' }))

        await waitFor(() => {
            expect(renameHistory).toHaveBeenCalled()
            expect(screen.getByLabelText('File Name')).toBeInTheDocument()
        })
    })

    it('opens delete dialog and confirms deletion', async () => {
        const deleteHistory = vi.fn().mockResolvedValue(true)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ deleteHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
        expect(screen.getByRole('dialog')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Delete History' }))

        await waitFor(() => {
            expect(deleteHistory).toHaveBeenCalledWith(historyItems[0].id)
        })
    })

    it('keeps delete dialog open when delete fails', async () => {
        const deleteHistory = vi.fn().mockResolvedValue(false)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ deleteHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
        fireEvent.click(screen.getByRole('button', { name: 'Delete History' }))

        await waitFor(() => {
            expect(deleteHistory).toHaveBeenCalledWith(historyItems[0].id)
        })

        expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('shows delete dialog pending state when confirmation is in progress', () => {
        const { rerender } = render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                deletingHistoryId: historyItems[0].id,
            })
        )
        rerender(<HistoryPage />)

        const dialog = screen.getByRole('dialog')
        expect(within(dialog).getByRole('button', { name: 'Deleting...' })).toBeDisabled()
    })

    it('shows delete dialog pending label when delete is in progress', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                deletingHistoryId: historyItems[0].id,
            })
        )

        render(<HistoryPage />)

        expect(screen.getByRole('button', { name: 'Deleting...' })).toBeDisabled()
    })

    it('closes delete dialog when cancel is clicked', () => {
        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
        expect(screen.getByRole('dialog')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('shows deleting state label when delete is pending', () => {
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                deletingHistoryId: historyItems[0].id,
            })
        )

        render(<HistoryPage />)

        expect(screen.getByRole('button', { name: 'Deleting...' })).toBeDisabled()
    })
})
