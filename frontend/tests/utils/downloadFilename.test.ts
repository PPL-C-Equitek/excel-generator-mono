import { describe, expect, it, vi } from 'vitest'
import { resolveDownloadFilename } from '../../src/utils/downloadFilename'

describe('resolveDownloadFilename', () => {
    it('returns the fallback when Content-Disposition is missing', () => {
        const headers = new Headers()

        expect(resolveDownloadFilename(headers, 'fallback.csv')).toBe('fallback.csv')
    })

    it('returns a decoded filename from filename*', () => {
        const headers = new Headers({
            'Content-Disposition': "attachment; filename*=UTF-8''report%20final.csv",
        })

        expect(resolveDownloadFilename(headers, 'fallback.csv')).toBe('report final.csv')
    })

    it('keeps the raw encoded filename when decodeURIComponent fails', () => {
        const headers = new Headers({
            'Content-Disposition': "attachment; filename*=UTF-8''%E0%A4%A",
        })

        expect(resolveDownloadFilename(headers, 'fallback.csv')).toBe('%E0%A4%A')
    })

    it('falls back from empty filename* to quoted filename', () => {
        const headers = new Headers({
            'Content-Disposition': 'attachment; filename*=   ; filename="quoted.csv"',
        })

        expect(resolveDownloadFilename(headers, 'fallback.csv')).toBe('quoted.csv')
    })

    it('falls back from invalid quoted filename to plain filename', () => {
        const headers = new Headers({
            'Content-Disposition': 'attachment; filename=plain.csv; filename=".."',
        })

        expect(resolveDownloadFilename(headers, 'fallback.csv')).toBe('plain.csv')
    })

    it('returns fallback when plain filename sanitizes to an invalid basename', () => {
        const headers = new Headers({
            'Content-Disposition': 'attachment; filename=..',
        })

        expect(resolveDownloadFilename(headers, 'fallback.csv')).toBe('fallback.csv')
    })

    it('returns fallback when a regex match exists without a captured filename value', () => {
        const headers = new Headers({
            'Content-Disposition': 'attachment; filename=report.csv',
        })
        const originalExec = RegExp.prototype.exec
        const execSpy = vi
            .spyOn(RegExp.prototype, 'exec')
            .mockImplementation(function (this: RegExp, value: string) {
                if (this.source === 'filename\\s*=\\s*([^;]+)') {
                    return ['filename='] as unknown as RegExpExecArray
                }

                return originalExec.call(this, value)
            })

        expect(resolveDownloadFilename(headers, 'fallback.csv')).toBe('fallback.csv')

        execSpy.mockRestore()
    })
})
