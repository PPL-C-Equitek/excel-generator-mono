import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
import type { HistoryItem } from '../../../src/services/history'
import type { SessionResume } from '../../../src/services/sessions'

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
    generateJson: vi.fn().mockResolvedValue('{}'),
}))

vi.mock('../../../src/components/Sidebar', async () => {
    const { default: HistorySidebarList } = await vi.importActual<typeof import('../../../src/components/HistorySidebarList')>(
        '../../../src/components/HistorySidebarList'
    )

    return {
        default: ({
            activeMenu,
            selectedHistoryId,
            historyListState,
        }: {
            activeMenu: string
            selectedHistoryId?: string | null
            historyListState?: {
                items: HistoryItem[]
                isLoading: boolean
                loadError: string | null
                renamingHistoryId: string | null
                deletingHistoryId: string | null
                reloadHistory: () => Promise<void>
                renameHistory: (historyId: string, customName: string) => Promise<boolean>
                deleteHistory: (historyId: string) => Promise<boolean>
            }
        }) => (
            <div data-testid="sidebar">
                <div data-testid="active-menu">{activeMenu}</div>
                <div data-testid="selected-history-id">{selectedHistoryId ?? 'none'}</div>
                {historyListState ? (
                    <HistorySidebarList
                        selectedHistoryId={selectedHistoryId ?? null}
                        items={historyListState.items}
                        isLoading={historyListState.isLoading}
                        loadError={historyListState.loadError}
                        renamingHistoryId={historyListState.renamingHistoryId}
                        deletingHistoryId={historyListState.deletingHistoryId}
                        reloadHistory={historyListState.reloadHistory}
                        renameHistory={historyListState.renameHistory}
                        deleteHistory={historyListState.deleteHistory}
                    />
                ) : null}
            </div>
        ),
    }
})

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

function makeSessionResumeState(sessionId: string): {
    session: SessionResume
    isLoading: boolean
    error: null
    isNotFound: boolean
} {
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
                    export_output_json: {
                        document_info: { filename: 'report-a.pdf', source_type: 'PDF' },
                    },
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

        expect(screen.getAllByText('Loading history...')).toHaveLength(2)
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

        expect(screen.getAllByText('Failed to load history.')).toHaveLength(2)
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

    it('groups history by created_at and falls back for invalid created_at', () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-05-10T00:00:00Z'))

        mockSearchParam(historyItems[0].id)
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [historyItems[0]],
                count: 1,
            })
        )
        const { unmount } = render(<HistoryPage />)
        expect(screen.getByText('Last 30 days')).toBeInTheDocument()

        unmount()

        mockSearchParam(historyItems[1].id)
        mockUseHistoryFiles.mockReturnValue(
            makeHookState({
                items: [historyItems[1]],
                count: 1,
            })
        )
        render(<HistoryPage />)
        expect(screen.getByText('Older')).toBeInTheDocument()

        vi.useRealTimers()
    })

    it('calls latest output download handlers when session output exists', async () => {
        const sessionId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        mockSessionSearchParam(historyItems[0].id, sessionId)
        mockUseSessionResume.mockReturnValue(makeSessionResumeState(sessionId))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }))
        fireEvent.click(screen.getByRole('button', { name: 'Download Excel' }))

        await waitFor(() => {
            expect(mockDownloadSessionOutputCsvFile).toHaveBeenCalledWith(
                sessionId,
                'output-1',
                'report-a.csv'
            )
            expect(mockDownloadSessionOutputExcelFile).toHaveBeenCalledWith(
                sessionId,
                'output-1',
                'report-a.xlsx'
            )
        })
    })

    it('allows rename flow and submits new name', async () => {
        const renameHistory = vi.fn().mockResolvedValue(true)
        mockUseHistoryFiles.mockReturnValue(makeHookState({ renameHistory }))

        render(<HistoryPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Actions for report-a.pdf' }))
        fireEvent.click(screen.getByRole('button', { name: 'Rename' }))

        const user = userEvent.setup()
        const nameInput = screen.getByLabelText('File Name')
        await user.clear(nameInput)
        await user.type(nameInput, 'Quarter 1 Report')
        await user.click(screen.getByRole('button', { name: 'Save' }))

        await waitFor(() => {
            expect(renameHistory).toHaveBeenCalledWith(
                historyItems[0].id,
                'Quarter 1 Report'
            )
        })
    })

    it('keeps the history conversation panel fixed while the message list owns scrolling', () => {
        render(<HistoryPage />)

        const fallbackMessage = screen.getByText(
            'Session context is not available for this history item, so per-session thinking logs cannot be loaded yet.'
        )
        const mainPanel = fallbackMessage.closest('main')
        const detailViewport = mainPanel?.querySelector('section > div')

        expect(mainPanel).toHaveClass('h-screen', 'overflow-hidden')
        expect(detailViewport).toHaveClass('overflow-hidden')
        expect(detailViewport).not.toHaveClass('overflow-y-auto')
    })

    it('does not render the removed detail metadata and action controls', () => {
        render(<HistoryPage />)

        expect(screen.queryByText('Status')).not.toBeInTheDocument()
        expect(screen.queryByText('Created at')).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Edit Name' })).not.toBeInTheDocument()
    })
})
