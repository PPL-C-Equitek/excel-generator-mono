import pdfplumber


class NonOCRPDFService:
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
            pages_content = []

            for page_number, page in enumerate(pdf.pages, start=1):
                page_data: list = []

                tables = page.extract_tables() or []
                table_bboxes = [t.bbox for t in page.find_tables()] if tables else []

                if tables:
                    # Collect text outside table regions
                    filtered_page = page
                    for bbox in table_bboxes:
                        filtered_page = filtered_page.outside_bbox(bbox)

                    outside_text = filtered_page.extract_text() or ""
                    outside_lines = outside_text.splitlines() if outside_text else []

                    # Add table rows
                    for table in tables:
                        for row in table:
                            page_data.append(
                                [cell if cell is not None else "" for cell in row]
                            )

                    # Add non-table text lines
                    for line in outside_lines:
                        stripped = line.strip()
                        if stripped:
                            page_data.append(stripped)
                else:
                    raw_text = page.extract_text() or ""
                    if raw_text:
                        page_data = raw_text.splitlines()
                    # else: page_data stays []

                pages_content.append(
                    {
                        "page": page_number,
                        "text": page_data,
                    }
                )

        return {
            "content": pages_content,
        }
