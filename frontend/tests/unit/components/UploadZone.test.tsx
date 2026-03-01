import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import UploadZone from '../../../src/components/UploadZone'

describe('UploadZone', () => {
  it('renders upload button and drop text', () => {
    render(<UploadZone />)
    expect(screen.getByText('Upload File')).toBeInTheDocument()
    expect(screen.getByText('Or drop file here')).toBeInTheDocument()
  })

  it('renders hidden file input', () => {
    render(<UploadZone />)
    const input = screen.getByTestId('file-input')
    expect(input).toHaveAttribute('type', 'file')
  })

  it('calls onFileSelect when file is chosen', async () => {
    const mockOnFileSelect = vi.fn()
    render(<UploadZone onFileSelect={mockOnFileSelect} />)

    const file = new File(['dummy'], 'test.pdf', { type: 'application/pdf' })
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, file)
    expect(mockOnFileSelect).toHaveBeenCalledWith(file)
  })

  it('shows file name after file is selected', async () => {
    render(<UploadZone />)
    const file = new File(['dummy'], 'laporan.pdf', { type: 'application/pdf' })
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, file)
    expect(screen.getByText('laporan.pdf')).toBeInTheDocument()
  })

  it('highlights drop zone when dragging over', () => {
    render(<UploadZone />)
    const dropZone = screen.getByTestId('drop-zone')

    fireEvent.dragOver(dropZone)
    expect(dropZone).toHaveClass('border-red-600')

    fireEvent.dragLeave(dropZone)
    expect(dropZone).not.toHaveClass('border-red-600')
  })
})