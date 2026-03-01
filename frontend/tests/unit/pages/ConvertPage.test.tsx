import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ConvertPage from '../../../src/app/convert/ConvertPage'

describe('ConvertPage', () => {
    it('renders page heading', () => {
        render(<ConvertPage />)
        expect(screen.getByText('Automate Your Data Structuring')).toBeInTheDocument()
    })

    it('renders subtitle text', () => {
        render(<ConvertPage />)
        expect(screen.getByText(/Replace manual entry/i)).toBeInTheDocument()
    })

    it('renders Sidebar and UploadZone together', () => {
        render(<ConvertPage />)
        expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        expect(screen.getByText('Upload File')).toBeInTheDocument()
    })
})