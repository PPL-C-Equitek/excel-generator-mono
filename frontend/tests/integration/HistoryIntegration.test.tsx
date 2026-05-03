import { render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import HistorySidebarList from '@/components/HistorySidebarList'
import { useHistoryFiles } from '@/hooks/useHistoryFiles'
import * as api from '@/lib/api'
import * as auth from '@/lib/auth'
import { getSessionResume } from '@/services/sessions'

vi.mock('@/services/sessions', () => ({
    getSessionResume: vi.fn(),
}))

const mockGetSessionResume = vi.mocked(getSessionResume)

function makeListState(
    overrides?: Partial<{
        items: Array<{
            id: string
            original_name: string
            custom_name: string
            status_processing: string
            created_at: string
            session_id?: string
        }>
        isLoading: boolean
        loadError: string | null
    }>
) {
    return {
        items: [],
        isLoading: false,
        loadError: null,
        renamingHistoryId: null,
        deletingHistoryId: null,
        reloadHistory: vi.fn().mockResolvedValue(undefined),
        renameHistory: vi.fn().mockResolvedValue(true),
        deleteHistory: vi.fn().mockResolvedValue(true),
        ...overrides,
    }
}

describe('History List -> Session Detail integration (RED)', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.clearAllMocks()
    })

    it('fetches history list data from /sessions endpoint', async () => {
        vi.spyOn(auth, 'getValidAccessToken').mockResolvedValue('access-token')
        const fetchSpy = vi.spyOn(api, 'fetchAPI').mockResolvedValue({
            count: 0,
            limit: 50,
            offset: 0,
            results: [],
        })

        const { result } = renderHook(() =>
            useHistoryFiles({ loadAll: true, pageSize: 50 })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(fetchSpy).toHaveBeenCalledWith(
            expect.stringMatching(/^sessions\/?/),
            expect.any(Object)
        )
    })

    it('renders "No history yet" when session list is empty', () => {
        render(<HistorySidebarList selectedHistoryId={null} {...makeListState()} />)

        expect(screen.getByText(/No history yet/i)).toBeInTheDocument()
    })

    it('clicking a session triggers resume loading with the selected sessionId', async () => {
        const user = userEvent.setup()
        const sessionId = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        const itemName = 'Session: Tax Report'

        render(
            <HistorySidebarList
                selectedHistoryId={null}
                {...makeListState({
                    items: [
                        {
                            id: '11111111-1111-1111-1111-111111111111',
                            original_name: itemName,
                            custom_name: '',
                            status_processing: 'completed',
                            created_at: '2026-05-01T08:00:00Z',
                            session_id: sessionId,
                        },
                    ],
                })}
            />
        )

        await user.click(screen.getByRole('link', { name: itemName }))

        expect(mockGetSessionResume).toHaveBeenCalledWith(sessionId)
    })
})
