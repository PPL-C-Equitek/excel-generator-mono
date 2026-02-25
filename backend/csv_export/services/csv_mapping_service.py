class CSVMappingService:
    def map_rows(self, headers, rows):
        return [[row[header] for header in headers] for row in rows]
