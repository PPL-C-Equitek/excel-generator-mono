import { describe, expect, it, vi } from 'vitest'
import {
    DeleteHistoryCommand,
    DownloadHistoryCommand,
    RenameHistoryCommand,
    createHistoryServiceCommandFactory,
} from '@/commands/historyCommands'
import type { HistoryItem } from '@/services/history'

const historyItem: HistoryItem = {
    id: 'history-1',
    original_name: 'report.pdf',
    custom_name: 'Report',
    status_processing: 'completed',
    created_at: '2026-04-10T10:00:00Z',
}

function makeService() {
    return {
        downloadHistoryFile: vi.fn().mockResolvedValue(undefined),
        renameHistoryFile: vi.fn().mockResolvedValue(historyItem),
        deleteHistoryFile: vi.fn().mockResolvedValue(undefined),
    }
}

describe('history commands', () => {
    it('executes download through the history service', async () => {
        const service = makeService()
        const command = new DownloadHistoryCommand(
            'history-1',
            'csv',
            'report.csv',
            service
        )

        await command.execute()

        expect(service.downloadHistoryFile).toHaveBeenCalledWith(
            'history-1',
            'csv',
            'report.csv'
        )
    })

    it('executes rename through the history service', async () => {
        const service = makeService()
        const command = new RenameHistoryCommand('history-1', 'Renamed Report', service)

        await expect(command.execute()).resolves.toEqual(historyItem)
        expect(service.renameHistoryFile).toHaveBeenCalledWith('history-1', 'Renamed Report')
    })

    it('executes delete through the history service', async () => {
        const service = makeService()
        const command = new DeleteHistoryCommand('history-1', service)

        await command.execute()

        expect(service.deleteHistoryFile).toHaveBeenCalledWith('history-1')
    })

    it('creates commands from a shared service factory', async () => {
        const service = makeService()
        const commands = createHistoryServiceCommandFactory(service)

        await commands.download('history-1', 'xlsx', 'report.xlsx').execute()
        await commands.rename('history-1', 'Factory Rename').execute()
        await commands.delete('history-1').execute()

        expect(service.downloadHistoryFile).toHaveBeenCalledWith(
            'history-1',
            'xlsx',
            'report.xlsx'
        )
        expect(service.renameHistoryFile).toHaveBeenCalledWith('history-1', 'Factory Rename')
        expect(service.deleteHistoryFile).toHaveBeenCalledWith('history-1')
    })
})
