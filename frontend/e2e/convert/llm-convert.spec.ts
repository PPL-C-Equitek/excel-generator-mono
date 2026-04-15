import { expect, test } from '@playwright/test'

const schemaId = '11111111-1111-1111-1111-111111111111'
const uploadErrorScenarios = [
  {
    title: 'maps oversized upload errors to the user-friendly message',
    backendMessage: 'File too large. Maximum allowed size is 10MB.',
    expectedMessage: 'File size too big.',
  },
  {
    title: 'maps password-protected excel upload errors to the user-friendly message',
    backendMessage: 'Excel file is password-protected.',
    expectedMessage: 'Excel is password-protected. Please remove the password and try again.',
  },
  {
    title: 'maps corrupted pdf upload errors to the user-friendly message',
    backendMessage: 'PDF file is corrupt.',
    expectedMessage: 'PDF file is corrupted or invalid.',
  },
] as const

test('convert sends selected schema id to llm and supports csv download', async ({ page }) => {
  let llmPayload: Record<string, unknown> | null = null
  let exportCsvPayload: Record<string, unknown> | null = null

  await page.route('**/schemas/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: schemaId,
          owner_id: 'owner-id',
          name: 'E2E Revenue Schema',
          description: 'Schema for e2e convert tests.',
          is_active: false,
          definition: {
            columns: [{ name: 'item', description: 'Line item name' }],
          },
          prompt_fragment: '',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ]),
    })
  })

  await page.route('**/upload/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        filename: 'stub-upload.pdf',
        size: 2048,
        document_info: {
          filename: 'stub-upload.pdf',
        },
      }),
    })
  })

  await page.route('**/llm/generate/', async (route) => {
    const rawBody = route.request().postData()
    llmPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        output_json: {
          summary: 'ok',
          rows: [{ item: 'Revenue', value: 1000 }],
        },
      }),
    })
  })

  await page.route('**/export/csv', async (route) => {
    const rawBody = route.request().postData()
    exportCsvPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ file_id: 'csv_e2e_1' }),
    })
  })

  await page.route('**/export/csv/csv_e2e_1/download**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/csv',
      headers: {
        'Content-Disposition': 'attachment; filename="result.csv"',
      },
      body: 'item,value\nRevenue,1000',
    })
  })

  await page.goto('/convert')

  await page.getByTestId('schema-select').selectOption(schemaId)
  await page.getByTestId('file-input').setInputFiles({
    name: 'input.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 e2e'),
  })
  await page.getByTestId('convert-btn').click()

  await expect(page.getByText('stub-upload.pdf')).toBeVisible()
  await expect(page.getByTestId('download-csv-btn')).toBeVisible()

  const exportCsvRequest = page.waitForResponse((response) => {
    return response.url().includes('/export/csv') && response.request().method() === 'POST'
  })
  await page.getByTestId('download-csv-btn').click()
  await exportCsvRequest

  expect(llmPayload).toMatchObject({
    custom_schema_id: schemaId,
  })
  expect(exportCsvPayload).toMatchObject({
    output_json: {
      summary: 'ok',
      rows: [{ item: 'Revenue', value: 1000 }],
    },
  })
})

test('convert handles excel download failure and retry succeeds', async ({ page }) => {
  let excelDownloadAttempts = 0

  await page.route('**/schemas/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  })

  await page.route('**/upload/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        filename: 'retry-upload.pdf',
        size: 1024,
      }),
    })
  })

  await page.route('**/llm/generate/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        output_json: {
          summary: 'ready',
          rows: [{ item: 'Cost', value: 250 }],
        },
      }),
    })
  })

  await page.route('**/export/excel', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        file_id: 'xlsx_retry_1',
        file_name: 'retry-upload.xlsx',
        artifact_type: 'xlsx',
      }),
    })
  })

  await page.route('**/export/excel/xlsx_retry_1/download', async (route) => {
    excelDownloadAttempts += 1

    if (excelDownloadAttempts === 1) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Failed' }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType:
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      body: 'excel-bytes',
    })
  })

  await page.goto('/convert')

  await page.getByTestId('file-input').setInputFiles({
    name: 'retry-input.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 retry'),
  })
  await page.getByTestId('convert-btn').click()

  await expect(page.getByTestId('download-excel-btn')).toBeVisible()
  await page.getByTestId('download-excel-btn').click()

  await expect(page.getByText('Failed to export')).toBeVisible()
  await expect(page.getByTestId('retry-excel-btn')).toBeVisible()

  await page.getByTestId('retry-excel-btn').click()
  await expect(page.getByText('Successfully downloaded')).toBeVisible()
  expect(excelDownloadAttempts).toBe(2)
})

test('convert omits custom schema id when no schema is selected', async ({ page }) => {
  let llmPayload: Record<string, unknown> | null = null

  await page.route('**/schemas/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: schemaId,
          owner_id: 'owner-id',
          name: 'Optional Schema',
          description: 'Schema can be selected or skipped.',
          is_active: false,
          definition: {
            columns: [{ name: 'item', description: 'Line item name' }],
          },
          prompt_fragment: '',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ]),
    })
  })

  await page.route('**/upload/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        filename: 'no-schema-upload.pdf',
        size: 1536,
      }),
    })
  })

  await page.route('**/llm/generate/', async (route) => {
    const rawBody = route.request().postData()
    llmPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        output_json: {
          summary: 'ok',
          rows: [{ item: 'Revenue', value: 1000 }],
        },
      }),
    })
  })

  await page.goto('/convert')

  await page.getByTestId('file-input').setInputFiles({
    name: 'noschema.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 no schema'),
  })
  await page.getByTestId('convert-btn').click()

  await expect(page.getByText('no-schema-upload.pdf')).toBeVisible()
  expect(llmPayload).not.toBeNull()
  expect(
    Object.prototype.hasOwnProperty.call(
      llmPayload as Record<string, unknown>,
      'custom_schema_id'
    )
  ).toBe(false)
})

test('convert shows an error when csv export response has invalid file id', async ({ page }) => {
  await page.route('**/schemas/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  })

  await page.route('**/upload/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        filename: 'invalid-csv-id.pdf',
        size: 1536,
      }),
    })
  })

  await page.route('**/llm/generate/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        output_json: {
          summary: 'ok',
          rows: [{ item: 'Revenue', value: 1000 }],
        },
      }),
    })
  })

  await page.route('**/export/csv', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ file_id: 'invalid_csv_1' }),
    })
  })

  await page.goto('/convert')

  await page.getByTestId('file-input').setInputFiles({
    name: 'invalid-csv-id.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 invalid csv'),
  })
  await page.getByTestId('convert-btn').click()
  await expect(page.getByTestId('download-csv-btn')).toBeVisible()

  await page.getByTestId('download-csv-btn').click()
  await expect(
    page.getByRole('alert').getByText('The export result is invalid. Please try again.')
  ).toBeVisible()
})

for (const scenario of uploadErrorScenarios) {
  test(scenario.title, async ({ page }) => {
    let llmRequestCount = 0

    await page.route('**/schemas/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })

    await page.route('**/upload/', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ message: scenario.backendMessage }),
      })
    })

    await page.route('**/llm/generate/', async (route) => {
      llmRequestCount += 1
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'unexpected' }),
      })
    })

    await page.goto('/convert')

    await page.getByTestId('file-input').setInputFiles({
      name: 'upload-error-case.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 upload error'),
    })
    await page.getByTestId('convert-btn').click()

    await expect(page.getByRole('alert').getByText(scenario.expectedMessage)).toBeVisible()
    await expect(page.getByTestId('download-csv-btn')).toHaveCount(0)
    expect(llmRequestCount).toBe(0)
  })
}

test('convert shows an error when llm generate returns an invalid response shape', async ({ page }) => {
  await page.route('**/schemas/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  })

  await page.route('**/upload/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        filename: 'invalid-llm-shape.pdf',
        size: 2048,
      }),
    })
  })

  await page.route('**/llm/generate/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ output_json: 'invalid-string-shape' }),
    })
  })

  await page.goto('/convert')

  await page.getByTestId('file-input').setInputFiles({
    name: 'invalid-llm-shape.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 invalid llm'),
  })
  await page.getByTestId('convert-btn').click()

  await expect(
    page.getByRole('alert').getByText('The server returned an invalid response.')
  ).toBeVisible()
  await expect(page.getByTestId('download-csv-btn')).toHaveCount(0)
  await expect(page.getByTestId('download-excel-btn')).toHaveCount(0)
})
