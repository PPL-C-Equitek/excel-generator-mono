import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import UploadZone from '../../../src/components/UploadZone'

// Mock module api
vi.mock('../../../src/lib/api', () => ({
  uploadFile: vi.fn(),
}))

import { uploadFile } from '../../../src/lib/api'

describe('UploadZone', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

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
    vi.mocked(uploadFile).mockResolvedValue({ filename: 'test.pdf' })

    const mockOnFileSelect = vi.fn()
    render(<UploadZone onFileSelect={mockOnFileSelect} />)

    const file = new File(['dummy'], 'test.pdf', { type: 'application/pdf' })
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(mockOnFileSelect).toHaveBeenCalledWith(file)
    })
  })

  it('shows file name after file is selected', async () => {
    vi.mocked(uploadFile).mockResolvedValue({ filename: 'laporan.pdf' })

    render(<UploadZone />)
    const file = new File(['dummy'], 'laporan.pdf', { type: 'application/pdf' })
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText('laporan.pdf')).toBeInTheDocument()
    })
  })

  it('highlights drop zone when dragging over', () => {
    render(<UploadZone />)
    const dropZone = screen.getByTestId('drop-zone')

    fireEvent.dragOver(dropZone)
    expect(dropZone).toHaveClass('border-red-600')

    fireEvent.dragLeave(dropZone)
    expect(dropZone).not.toHaveClass('border-red-600')
  })

  it('shows loading state while uploading', async () => {
    vi.mocked(uploadFile).mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000))
    )

    render(<UploadZone />)
    const file = new File(['dummy'], 'test.pdf', { type: 'application/pdf' })
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, file)
    expect(screen.getByText('Uploading...')).toBeInTheDocument()
  })

  it('shows error message when upload fails', async () => {
    vi.mocked(uploadFile).mockRejectedValue(new Error('No file provided'))

    render(<UploadZone />)
    const file = new File(['dummy'], 'test.pdf', { type: 'application/pdf' })
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText('No file provided')).toBeInTheDocument()
    })
  })
})