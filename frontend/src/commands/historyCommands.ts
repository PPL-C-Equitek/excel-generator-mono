import type { HistoryItem } from '@/services/history'

export type HistoryFileFormat = 'csv' | 'xlsx'

export interface HistoryCommand<TResult = void> {
    execute(): Promise<TResult>
}

export interface HistoryActionService {
    downloadHistoryFile: (
        historyId: string,
        fileFormat: HistoryFileFormat,
        filename?: string
    ) => Promise<void>
    renameHistoryFile: (historyId: string, customName: string) => Promise<HistoryItem>
    deleteHistoryFile: (historyId: string) => Promise<void>
}

export class CallbackHistoryCommand<TResult> implements HistoryCommand<TResult> {
    constructor(private readonly action: () => Promise<TResult>) {}

    execute(): Promise<TResult> {
        return this.action()
    }
}

export class DownloadHistoryCommand implements HistoryCommand<void> {
    constructor(
        private readonly historyId: string,
        private readonly fileFormat: HistoryFileFormat,
        private readonly filename: string | undefined,
        private readonly service: HistoryActionService
    ) {}

    execute(): Promise<void> {
        return this.service.downloadHistoryFile(this.historyId, this.fileFormat, this.filename)
    }
}

export class RenameHistoryCommand implements HistoryCommand<HistoryItem> {
    constructor(
        private readonly historyId: string,
        private readonly customName: string,
        private readonly service: HistoryActionService
    ) {}

    execute(): Promise<HistoryItem> {
        return this.service.renameHistoryFile(this.historyId, this.customName)
    }
}

export class DeleteHistoryCommand implements HistoryCommand<void> {
    constructor(
        private readonly historyId: string,
        private readonly service: HistoryActionService
    ) {}

    execute(): Promise<void> {
        return this.service.deleteHistoryFile(this.historyId)
    }
}

export interface HistoryServiceCommandFactory {
    download: (
        historyId: string,
        fileFormat: HistoryFileFormat,
        filename?: string
    ) => HistoryCommand<void>
    rename: (historyId: string, customName: string) => HistoryCommand<HistoryItem>
    delete: (historyId: string) => HistoryCommand<void>
}

export function createHistoryServiceCommandFactory(
    service: HistoryActionService
): HistoryServiceCommandFactory {
    return {
        download: (historyId, fileFormat, filename) =>
            new DownloadHistoryCommand(historyId, fileFormat, filename, service),
        rename: (historyId, customName) =>
            new RenameHistoryCommand(historyId, customName, service),
        delete: (historyId) => new DeleteHistoryCommand(historyId, service),
    }
}
