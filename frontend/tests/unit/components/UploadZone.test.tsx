import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest'
import UploadZone from '../../../src/components/UploadZone'

// Mock module api with stub pattern
vi.mock('../../../src/lib/api', () => ({
  uploadFile: vi.fn(),
}))

import { uploadFile } from '../../../src/lib/api'

// Test utilities - Factory pattern for test data
const createMockFile = (
  name = 'test.pdf',
  type = 'application/pdf',
  content = 'dummy content'
) => {
  return new File([content], name, { type })
}

interface MockDataTransfer {
  files: File[]
}

const createDragEvent = (files: File[]): Partial<DragEvent> => {
  return {
    dataTransfer: {
      files: files as any,
    } as DataTransfer,
    preventDefault: vi.fn(),
  }
}

describe('UploadZone', () => {
  const mockUploadFile = uploadFile as Mock

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

    it('renders button with correct initial state', () => {
      render(<UploadZone />)
      const button = screen.getByText('Upload File')
      expect(button).not.toBeDisabled()
      expect(button).toHaveClass('bg-red-700', 'text-white')
    })

    it('renders drop zone with default styling', () => {
      render(<UploadZone />)
      const dropZone = screen.getByTestId('drop-zone')
      expect(dropZone).toHaveClass('border-2', 'border-dashed', 'border-gray-300')
    })

    it('does not show error or file name initially', () => {
      render(<UploadZone />)
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument()
      expect(screen.getByText('Or drop file here')).toBeInTheDocument()
    })
  })

  describe('File Selection via Input', () => {
    it('calls onFileSelect when file is chosen', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

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

    it('shows file name after file is selected', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'laporan.pdf' })

      render(<UploadZone />)
      const file = createMockFile('laporan.pdf')
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        expect(screen.getByText('laporan.pdf')).toBeInTheDocument()
      })
    })

    it('triggers file input click when button is clicked', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

      render(<UploadZone />)
      const button = screen.getByText('Upload File')
      const input = screen.getByTestId('file-input') as HTMLInputElement

      const clickSpy = vi.spyOn(input, 'click')

      await userEvent.click(button)

      expect(clickSpy).toHaveBeenCalled()
    })

    it('handles multiple file selections correctly', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

      const mockOnFileSelect = vi.fn()
      render(<UploadZone onFileSelect={mockOnFileSelect} />)

      const input = screen.getByTestId('file-input')

      const file1 = createMockFile('file1.pdf')
      await userEvent.upload(input, file1)
      await waitFor(() => expect(mockOnFileSelect).toHaveBeenCalledWith(file1))

      mockUploadFile.mockResolvedValue({ filename: 'file2.pdf' })
      const file2 = createMockFile('file2.pdf')
      await userEvent.upload(input, file2)
      await waitFor(() => expect(mockOnFileSelect).toHaveBeenCalledWith(file2))

      expect(mockOnFileSelect).toHaveBeenCalledTimes(2)
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
      mockUploadFile.mockResolvedValue({ filename: 'dropped.pdf' })

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

    it('handles drag over event correctly', () => {
      render(<UploadZone />)
      const dropZone = screen.getByTestId('drop-zone')

      // Drag over should not throw and should change visual state
      expect(() => fireEvent.dragOver(dropZone)).not.toThrow()
      expect(dropZone).toHaveClass('border-red-600')
    })

    it('handles drop event and processes file', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

      render(<UploadZone />)
      const dropZone = screen.getByTestId('drop-zone')

      const file = createMockFile()
      const dragEvent = createDragEvent([file])

      // Drop should not throw
      expect(() => fireEvent.drop(dropZone, dragEvent)).not.toThrow()

      // File should be processed
      await waitFor(() => {
        expect(mockUploadFile).toHaveBeenCalledWith(file)
      })
    })

    it('resets drag state after drop', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

      render(<UploadZone />)
      const dropZone = screen.getByTestId('drop-zone')

      fireEvent.dragOver(dropZone)
      expect(dropZone).toHaveClass('border-red-600')

      const file = createMockFile()
      const dragEvent = createDragEvent([file])
      fireEvent.drop(dropZone, dragEvent)

      await waitFor(() => {
        expect(dropZone).not.toHaveClass('border-red-600')
      })
    })
  })

  describe('Loading States', () => {
    it('shows loading state while uploading', async () => {
      mockUploadFile.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ filename: 'test.pdf' }), 1000))
      )

      render(<UploadZone />)
      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)
      expect(screen.getByText('Uploading...')).toBeInTheDocument()
    })

    it('disables button while uploading', async () => {
      mockUploadFile.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ filename: 'test.pdf' }), 1000))
      )

      render(<UploadZone />)
      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      const button = screen.getByText('Uploading...')
      expect(button).toBeDisabled()
    })

    it('re-enables button after upload completes', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

      render(<UploadZone />)
      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        const button = screen.getByText('Upload File')
        expect(button).not.toBeDisabled()
      })
    })
  })

  describe('Error Handling', () => {
    it('shows error message when upload fails', async () => {
      mockUploadFile.mockRejectedValue(new Error('No file provided'))

      render(<UploadZone />)
      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        expect(screen.getByText('No file provided')).toBeInTheDocument()
      })
    })

    it('handles non-Error rejection objects', async () => {
      mockUploadFile.mockRejectedValue('String error')

      render(<UploadZone />)
      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        expect(screen.getByText('Upload failed')).toBeInTheDocument()
      })
    })

    it('clears previous error on new upload', async () => {
      mockUploadFile.mockRejectedValueOnce(new Error('First error'))
      mockUploadFile.mockResolvedValueOnce({ filename: 'success.pdf' })

      render(<UploadZone />)
      const input = screen.getByTestId('file-input')

      // First upload fails
      const file1 = createMockFile('fail.pdf')
      await userEvent.upload(input, file1)
      await waitFor(() => expect(screen.getByText('First error')).toBeInTheDocument())

      // Second upload succeeds
      const file2 = createMockFile('success.pdf')
      await userEvent.upload(input, file2)

      await waitFor(() => {
        expect(screen.queryByText('First error')).not.toBeInTheDocument()
        expect(screen.getByText('success.pdf')).toBeInTheDocument()
      })
    })

    it('does not show file name when error occurs', async () => {
      mockUploadFile.mockRejectedValue(new Error('Upload error'))

      render(<UploadZone />)
      const file = createMockFile('error-file.pdf')
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        expect(screen.getByText('Upload error')).toBeInTheDocument()
        expect(screen.queryByText('error-file.pdf')).not.toBeInTheDocument()
      })
    })
  })

  describe('API Integration', () => {
    it('calls uploadFile API with correct file', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

      render(<UploadZone />)
      const file = createMockFile('api-test.pdf', 'application/pdf', 'content')
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        expect(mockUploadFile).toHaveBeenCalledWith(file)
        expect(mockUploadFile).toHaveBeenCalledTimes(1)
      })
    })

    it('waits for API response before calling onFileSelect', async () => {
      const mockOnFileSelect = vi.fn()
      let resolveUpload: (value: any) => void

      mockUploadFile.mockReturnValue(
        new Promise((resolve) => {
          resolveUpload = resolve
        })
      )

      render(<UploadZone onFileSelect={mockOnFileSelect} />)
      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      // Should not be called yet
      expect(mockOnFileSelect).not.toHaveBeenCalled()

      // Resolve the upload
      resolveUpload!({ filename: 'test.pdf' })

      await waitFor(() => {
        expect(mockOnFileSelect).toHaveBeenCalledWith(file)
      })
    })
  })

  describe('Edge Cases and Component Behavior', () => {
    it('works without onFileSelect callback', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

      render(<UploadZone />)
      const file = createMockFile()
      const input = screen.getByTestId('file-input')

      await expect(userEvent.upload(input, file)).resolves.not.toThrow()

      await waitFor(() => {
        expect(screen.getByText('test.pdf')).toBeInTheDocument()
      })
    })

    it('handles rapid drag over and leave events', () => {
      render(<UploadZone />)
      const dropZone = screen.getByTestId('drop-zone')

      for (let i = 0; i < 5; i++) {
        fireEvent.dragOver(dropZone)
        fireEvent.dragLeave(dropZone)
      }

      expect(dropZone).not.toHaveClass('border-red-600')
    })

    it('handles empty file drop gracefully', async () => {
      render(<UploadZone />)
      const dropZone = screen.getByTestId('drop-zone')

      const event = {
        preventDefault: vi.fn(),
        dataTransfer: { files: [] as any },
      }

      expect(() => fireEvent.drop(dropZone, event)).not.toThrow()
    })

    it('updates state correctly on successful upload', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'success.pdf' })

      render(<UploadZone />)
      const file = createMockFile('success.pdf')
      const input = screen.getByTestId('file-input')

      await userEvent.upload(input, file)

      await waitFor(() => {
        expect(screen.getByText('success.pdf')).toBeInTheDocument()
        expect(screen.queryByText('Uploading...')).not.toBeInTheDocument()
        expect(screen.queryByText(/drop file here/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Component Lifecycle', () => {
    it('cleans up properly on unmount', () => {
      const { unmount } = render(<UploadZone />)
      expect(() => unmount()).not.toThrow()
    })

    it('can be re-rendered with different props', () => {
      const mockCallback1 = vi.fn()
      const mockCallback2 = vi.fn()

      const { rerender } = render(<UploadZone onFileSelect={mockCallback1} />)
      rerender(<UploadZone onFileSelect={mockCallback2} />)

      expect(screen.getByText('Upload File')).toBeInTheDocument()
    })
  })
})