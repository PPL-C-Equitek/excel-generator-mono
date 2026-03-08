import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
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

  describe('File Selection via Input', () => {
    it('calls onFileSelect when file is chosen', async () => {
      const mockOnFileSelect = vi.fn()
      render(<UploadZone onFileSelect={mockOnFileSelect} />)

      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        expect(mockOnFileSelect).toHaveBeenCalledWith(file)
        expect(mockOnFileSelect).toHaveBeenCalledTimes(1)
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

    it('handles file drop correctly', async () => {
      const mockOnFileSelect = vi.fn()
      render(<UploadZone onFileSelect={mockOnFileSelect} />)

      const dropZone = screen.getByTestId('drop-zone')
      const file = createMockFile('dropped.pdf')

      const dragEvent = createDragEvent([file])
      fireEvent.drop(dropZone, dragEvent)

      await waitFor(() => {
        expect(mockOnFileSelect).toHaveBeenCalledWith(file)
      })
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
})