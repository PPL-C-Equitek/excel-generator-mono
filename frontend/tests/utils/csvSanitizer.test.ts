import { describe, it, expect } from 'vitest'
import { sanitizeCSVCell } from '../../src/utils/csvSanitizer'

describe('sanitizeCSVCell', () => {
    it('prepends single quote to strings starting with =', () => {
        expect(sanitizeCSVCell('=1+2')).toBe("'=" + "1+2")
    })

    it('prepends single quote to strings starting with +', () => {
        expect(sanitizeCSVCell('+1+2')).toBe("'+1+2")
    })

    it('prepends single quote to strings starting with -', () => {
        expect(sanitizeCSVCell('-cmd')).toBe("'-cmd")
    })

    it('prepends single quote to strings starting with @', () => {
        expect(sanitizeCSVCell('@sum(A1:A2)')).toBe("'@sum(A1:A2)")
    })

    it('does not modify normal strings', () => {
        expect(sanitizeCSVCell('hello world')).toBe('hello world')
        expect(sanitizeCSVCell('12345')).toBe('12345')
        expect(sanitizeCSVCell('a=b')).toBe('a=b') // = not at the start
    })

    it('escapes leading-space formula values', () => {
        expect(sanitizeCSVCell(' =SUM(A1:A2)')).toBe("' =SUM(A1:A2)")
        expect(sanitizeCSVCell(' +1')).toBe("' +1")
        expect(sanitizeCSVCell(' @cmd')).toBe("' @cmd")
        expect(sanitizeCSVCell(' hello')).toBe(' hello')
    })

    it('maps over array elements recursively', () => {
        const input = ['=1', 'hello', ['-2', 'world']]
        const expected = ["'=1", 'hello', ["'-2", 'world']]
        expect(sanitizeCSVCell(input)).toEqual(expected)
    })

    it('handles tab-prefixed formulas in nested arrays', () => {
        const input = ['safe', ['\t=SUM(A1:A2)']]
        const expected = ['safe', ["'\t=SUM(A1:A2)"]]
        expect(sanitizeCSVCell(input)).toEqual(expected)
    })

    it('maps over object values recursively without mutating original', () => {
        const input = {
            a: '=1',
            b: 'hello',
            c: {
                d: '-2',
                e: ['@sum']
            }
        }
        const expected = {
            a: "'=1",
            b: 'hello',
            c: {
                d: "'-2",
                e: ["'@sum"]
            }
        }
        
        const output = sanitizeCSVCell(input)
        expect(output).toEqual(expected)
        expect(output).not.toBe(input) // checks for deep copy / non-mutating
    })

    it('preserves plain object prototype', () => {
        const input = { a: '=1' }
        const output = sanitizeCSVCell(input) as Record<string, unknown>
        
        expect(output).toEqual({ a: "'=1" })
        expect(output).not.toBe(input)
        expect(Object.getPrototypeOf(output)).toBe(Object.prototype)
    })

    it('returns null and numbers as is', () => {
        expect(sanitizeCSVCell(null)).toBe(null)
        expect(sanitizeCSVCell(123)).toBe(123)
        expect(sanitizeCSVCell(undefined)).toBe(undefined)
        expect(sanitizeCSVCell(true)).toBe(true)
    })
})
