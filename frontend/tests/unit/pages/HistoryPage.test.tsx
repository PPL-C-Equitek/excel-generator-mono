import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSearchParams } from 'next/navigation'
import HistoryPage from '../../../src/app/history/HistoryPage'
import { useHistoryFiles } from '../../../src/hooks/useHistoryFiles'
import { useSessionResume } from '../../../src/hooks/useSessionResume'
import { useSessionThinkingLogs } from '../../../src/hooks/useSessionThinkingLogs'

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
        expect(screen.queryByRole('button', { name: 'Download latest as CSV' })).not.toBeInTheDocument()
    })
})
