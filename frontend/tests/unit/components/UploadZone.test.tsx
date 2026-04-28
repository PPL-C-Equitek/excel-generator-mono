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

    it('does not render follow-up chat before a file is generated', () => {
      render(<UploadZone />)
      expect(screen.queryByLabelText('Follow-up message')).not.toBeInTheDocument()
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

  it('shows schema/footer content below upload before and after a file is staged', async () => {
    render(<UploadZone footerContent={<div>Footer note</div>} />)

    expect(screen.getByText('Footer note')).toBeInTheDocument()

    await uploadAndStageFile(createMockFile('schema-context.pdf'))

    expect(screen.getByText('Footer note')).toBeInTheDocument()
  })

  it('sends follow-up chat with the submitted file after result content appears', async () => {
    const mockOnFileSelect = vi.fn()
    const { rerender } = render(<UploadZone onFileSelect={mockOnFileSelect} />)

    const file = await uploadAndStageFile(createMockFile('follow-up.pdf'))
    await userEvent.click(screen.getByTestId('convert-btn'))

    rerender(
      <UploadZone
        onFileSelect={mockOnFileSelect}
        resultContent={<p>Your file is ready.</p>}
      />
    )

    await userEvent.type(screen.getByLabelText('Follow-up message'), 'Refine the invoice rows')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    expect(mockOnFileSelect).toHaveBeenNthCalledWith(1, file)
    expect(mockOnFileSelect).toHaveBeenNthCalledWith(2, file, 'Refine the invoice rows')
  })

  it('keeps completed assistant results before follow-up prompts and latest results', async () => {
    const mockOnFileSelect = vi.fn()
    const { rerender } = render(<UploadZone onFileSelect={mockOnFileSelect} />)

    await uploadAndStageFile(createMockFile('few-shot.pdf'))
    await userEvent.click(screen.getByTestId('convert-btn'))

    rerender(
      <UploadZone
        onFileSelect={mockOnFileSelect}
        resultContent={<p>Initial file is ready.</p>}
      />
    )

    await userEvent.type(screen.getByLabelText('Follow-up message'), 'Only keep paid invoices')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    rerender(
      <UploadZone
        onFileSelect={mockOnFileSelect}
        resultContent={<p>Latest refined file is ready.</p>}
      />
    )

    const pageText = document.body.textContent ?? ''
    const initialResultIndex = pageText.indexOf('Initial file is ready.')
    const promptIndex = pageText.indexOf('Only keep paid invoices')
    const latestResultIndex = pageText.indexOf('Latest refined file is ready.')

    expect(initialResultIndex).toBeGreaterThan(-1)
    expect(promptIndex).toBeGreaterThan(initialResultIndex)
    expect(latestResultIndex).toBeGreaterThan(promptIndex)
  })

  it('shows selected schema context in the submitted file bubble', async () => {
    const mockOnFileSelect = vi.fn()
    const { rerender } = render(
      <UploadZone
        onFileSelect={mockOnFileSelect}
        selectedSchemaName="Invoice Mapping"
      />
    )

    await uploadAndStageFile(createMockFile('schema-bubble.pdf'))
    await userEvent.click(screen.getByTestId('convert-btn'))

    rerender(
      <UploadZone
        onFileSelect={mockOnFileSelect}
        selectedSchemaName="Invoice Mapping"
        resultContent={<p>Your file is ready.</p>}
      />
    )

    expect(screen.getByText('Schema context')).toBeInTheDocument()
    expect(screen.getByText('Invoice Mapping')).toBeInTheDocument()
  })

  it('renders assistant result content inside the chat surface after submit', async () => {
    const { rerender } = render(<UploadZone onFileSelect={vi.fn()} />)

    await uploadAndStageFile(createMockFile('ready.pdf'))
    await userEvent.click(screen.getByTestId('convert-btn'))

    rerender(<UploadZone onFileSelect={vi.fn()} resultContent={<button>Download CSV</button>} />)

    expect(screen.getByRole('button', { name: 'Download CSV' })).toBeInTheDocument()
  })

  it('keeps validation errors on the upload page instead of opening chat', async () => {
    const mockOnFileSelect = vi.fn()
    render(
      <UploadZone
        onFileSelect={mockOnFileSelect}
        isValidating={false}
        validationError="File is password-protected."
      />
    )

    await uploadAndStageFile(createMockFile('invalid.pdf'))
    await userEvent.click(screen.getByTestId('convert-btn'))

    expect(screen.getByRole('alert')).toHaveTextContent('File is password-protected.')
    expect(screen.getByTestId('convert-btn')).toBeInTheDocument()
    expect(screen.queryByLabelText('Follow-up message')).not.toBeInTheDocument()
  })

  it('clears stale validation errors when a new file is staged', async () => {
    const mockOnFileChange = vi.fn()
    render(
      <UploadZone
        onFileChange={mockOnFileChange}
        validationError="Unsupported file type."
      />
    )

    await uploadAndStageFile(createMockFile('invalid.txt', 'text/plain'))
    await userEvent.click(screen.getByTestId('convert-btn'))

    expect(screen.getByRole('alert')).toHaveTextContent('Unsupported file type.')

    await userEvent.click(screen.getByText('Change File'))
    await uploadAndStageFile(createMockFile('valid.pdf', 'application/pdf'))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('valid.pdf')).toBeInTheDocument()
    expect(mockOnFileChange).toHaveBeenCalledTimes(3)
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
