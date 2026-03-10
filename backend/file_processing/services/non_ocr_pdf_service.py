import pdfplumber


class NonOCRPDFService:
    @staticmethod
    def extract_table_rows(tables):
        """Convert table data into lists of cell strings."""
        rows = []
        for table in tables:
            for row in table:
                rows.append([cell if cell is not None else "" for cell in row])
        return rows

    @staticmethod
    def extract_text_outside_tables(page, table_bboxes):
        """Return non-empty text lines found outside table regions."""
        filtered_page = page
        for bbox in table_bboxes:
            filtered_page = filtered_page.outside_bbox(bbox)
        outside_text = filtered_page.extract_text() or ""
        return [line.strip() for line in outside_text.splitlines() if line.strip()]

    @staticmethod
    def extract_page_data(page):
        """Extract structured data from a single PDF page."""
        tables = page.extract_tables() or []

        if not tables:
            raw_text = page.extract_text() or ""
            return raw_text.splitlines() if raw_text else []

        table_bboxes = [t.bbox for t in page.find_tables()]
        page_data = NonOCRPDFService.extract_table_rows(tables)
        page_data.extend(
            NonOCRPDFService.extract_text_outside_tables(page, table_bboxes)
        )
        return page_data

    @staticmethod
    def extract_non_ocr_pdf_to_json(file_path: str) -> dict:
        """
        Extract text content from a non-OCR PDF file and return structured JSON.

        Each page is parsed for tables first (via pdfplumber). If tables are found,
        each row becomes a list of cell strings. Any text outside tables is captured
        as plain-text lines. If no tables are detected the page text is split into
        individual lines.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            dict with structure:
            {
                "content": [
                    {
                        "page": 1,
                        "text": [
                            ["col1", "col2", ...],   // table row
                            ["col1", "col2", ...],
                            "plain text line",        // non-table text
                        ]
                    },
                    ...
                ]
            }

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        with pdfplumber.open(file_path) as pdf:
            pages_content = [
                {
                    "page": page_number,
                    "text": NonOCRPDFService.extract_page_data(page),
                }
                for page_number, page in enumerate(pdf.pages, start=1)
            ]

        return {"content": pages_content}
