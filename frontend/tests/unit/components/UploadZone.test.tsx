import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import UploadZone from '../../../src/components/UploadZone'

// Test utilities
const createMockFile = (
  name = 'test.pdf',
  type = 'application/pdf',
  content = 'dummy content'
) => {
  return new File([content], name, { type })
}

const createDragEvent = (files: File[]): Partial<DragEvent> => {
  return {
    dataTransfer: {
      files: files as unknown as FileList,
    } as DataTransfer,
    preventDefault: vi.fn(),
  }
}

async function uploadAndStageFile(file = createMockFile()) {
  await userEvent.upload(screen.getByTestId('file-input'), file)
  return file
}

describe('UploadZone', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Initial Rendering', () => {
    it('renders upload button and drop text', () => {
      render(<UploadZone />)
      expect(screen.getByText('Upload File')).toBeInTheDocument()
      expect(screen.getByText('Or drop file here')).toBeInTheDocument()
    })

    it('renders hidden file input with correct attributes', () => {
      render(<UploadZone />)
      const input = screen.getByTestId('file-input')
      expect(input).toHaveAttribute('type', 'file')
      expect(input).toHaveClass('hidden')
    })
  })

  it('does nothing when input change has no file', () => {
    const mockOnFileSelect = vi.fn()
    render(<UploadZone onFileSelect={mockOnFileSelect} />)

    const input = screen.getByTestId('file-input')
    fireEvent.change(input, { target: { files: undefined } })

    expect(mockOnFileSelect).not.toHaveBeenCalled()
  })
})

describe('Drag and Drop Functionality', () => {
  it('highlights drop zone when dragging over', () => {
    render(<UploadZone />)
    const dropZone = screen.getByTestId('drop-zone')

    fireEvent.dragOver(dropZone)
    expect(dropZone).toHaveClass('border-red-600', 'bg-red-50')
  })

  it('removes highlight when drag leaves', () => {
    render(<UploadZone />)
    const dropZone = screen.getByTestId('drop-zone')

    fireEvent.dragOver(dropZone)
    expect(dropZone).toHaveClass('border-red-600')

    fireEvent.dragLeave(dropZone)
    expect(dropZone).not.toHaveClass('border-red-600')
    expect(dropZone).toHaveClass('border-gray-300')
  })

  it('handles empty file drop gracefully', async () => {
    const mockOnFileSelect = vi.fn()
    render(<UploadZone onFileSelect={mockOnFileSelect} />)
    const dropZone = screen.getByTestId('drop-zone')

    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { files: [] as unknown as FileList },
    }

    expect(() => fireEvent.drop(dropZone, event)).not.toThrow()
    expect(mockOnFileSelect).not.toHaveBeenCalled()
  })

  it('does not stage file or update UI when dropped file list is empty', () => {
    render(<UploadZone />)

    fireEvent.drop(screen.getByTestId('drop-zone'), {
      preventDefault: vi.fn(),
      dataTransfer: { files: [] as unknown as FileList },
    })

    expect(screen.getByTestId('drop-zone')).toBeInTheDocument()
    expect(screen.queryByTestId('convert-btn')).not.toBeInTheDocument()
  })

  it('stages a dropped file and shows its name in the confirmation state', () => {
    const file = createMockFile('dropped.pdf')
    render(<UploadZone footerContent={<div>Footer note</div>} />)

    fireEvent.drop(screen.getByTestId('drop-zone'), {
      preventDefault: vi.fn(),
      dataTransfer: { files: [file] as unknown as FileList },
    })

    expect(screen.getByText('dropped.pdf')).toBeInTheDocument()
    expect(screen.getByText('Footer note')).toBeInTheDocument()
    expect(screen.getByTestId('convert-btn')).toBeInTheDocument()
  })
})

describe('Disabled State', () => {
  it('disables input when disabled prop is true', () => {
    render(<UploadZone disabled={true} />)
    const input = screen.getByTestId('file-input')
    expect(input).toBeDisabled()
  })

  it('does not highlight on drag over when disabled', () => {
    render(<UploadZone disabled={true} />)
    const dropZone = screen.getByTestId('drop-zone')
    fireEvent.dragOver(dropZone)
    expect(dropZone).not.toHaveClass('border-red-600', 'bg-red-50')
  })

  it('does not handle drop when disabled', () => {
    const mockOnFileSelect = vi.fn()
    render(<UploadZone onFileSelect={mockOnFileSelect} disabled={true} />)
    const dropZone = screen.getByTestId('drop-zone')
    const file = createMockFile('dropped.pdf')
    const dragEvent = createDragEvent([file])
    fireEvent.drop(dropZone, dragEvent)
    expect(mockOnFileSelect).not.toHaveBeenCalled()
  })
})

describe('File Confirmation', () => {
  it('resets back to upload zone when "Change File" is clicked', async () => {
    render(<UploadZone />)

    await uploadAndStageFile()
    await userEvent.click(screen.getByText('Change File'))

    expect(screen.getByTestId('drop-zone')).toBeInTheDocument()
  })

  it('does not call onFileSelect when Convert is clicked without a file staged', async () => {
    const mockOnFileSelect = vi.fn()
    render(<UploadZone onFileSelect={mockOnFileSelect} />)

    await uploadAndStageFile()
    await userEvent.click(screen.getByText('Change File'))

    expect(screen.queryByTestId('convert-btn')).not.toBeInTheDocument()
    expect(mockOnFileSelect).not.toHaveBeenCalled()
  })

  it('calls onFileSelect with the staged file when Convert is clicked', async () => {
    const mockOnFileSelect = vi.fn()
    render(<UploadZone onFileSelect={mockOnFileSelect} />)

    const file = await uploadAndStageFile(createMockFile('convert-me.pdf'))
    await userEvent.click(screen.getByTestId('convert-btn'))

    expect(mockOnFileSelect).toHaveBeenCalledTimes(1)
    expect(mockOnFileSelect).toHaveBeenCalledWith(file)
  })

  it('displays file size in B for files under 1 KB', async () => {
    render(<UploadZone />)
    const file = new File(['hi'], 'small.pdf', { type: 'application/pdf' }) // 2 bytes
    await userEvent.upload(screen.getByTestId('file-input'), file)

    expect(screen.getByText('2 B')).toBeInTheDocument()
  })

  it('displays file size in KB for files between 1 KB and 1 MB', async () => {
    render(<UploadZone />)
    const file = new File([new Uint8Array(2048)], 'medium.pdf', { type: 'application/pdf' }) // 2 KB
    await userEvent.upload(screen.getByTestId('file-input'), file)

    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
  })

  it('displays file size in MB for files 1 MB and above', async () => {
    render(<UploadZone />)
    const file = new File([new Uint8Array(2 * 1024 * 1024)], 'large.pdf', { type: 'application/pdf' }) // 2 MB
    await userEvent.upload(screen.getByTestId('file-input'), file)

    expect(screen.getByText('2.0 MB')).toBeInTheDocument()
  })
})
