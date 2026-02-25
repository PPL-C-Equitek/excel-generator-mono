class CSVMappingService:
    def map_rows(self, headers, rows):
        if not headers:
            raise ValueError("headers must not be empty")

        return [[row[header] for header in headers] for row in rows]
