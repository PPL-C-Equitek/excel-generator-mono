import os
import re
import zipfile
import xml.etree.ElementTree as ET

try:
    import olefile
except Exception:  # pragma: no cover - optional dependency in local environments
    olefile = None


WORD_CORRUPT_ERROR = "Word file is corrupt or has an invalid structure."
DOC_UNREADABLE_TEXT_ERROR = "Unable to extract readable text from legacy .doc file."


class WordExtractionService:
    """Extract plain text content from Word files into a unified JSON shape."""

    @classmethod
    def extract_word_to_json(cls, file_path: str, ext: str | None = None):
        normalized_ext = (ext or os.path.splitext(file_path)[1]).lower()

        if normalized_ext == ".docx":
            return cls._extract_docx_to_json(file_path)

        if normalized_ext == ".doc":
            return cls._extract_doc_to_json(file_path)

        raise ValueError("Unsupported Word file type.")

    @staticmethod
    def _extract_docx_to_json(file_path: str):
        try:
            with zipfile.ZipFile(file_path) as archive:
                xml_bytes = archive.read("word/document.xml")
        except Exception as exc:
            raise ValueError(WORD_CORRUPT_ERROR) from exc

        lines = []
        root = ET.fromstring(xml_bytes)

        for paragraph in root.iter():
            if WordExtractionService._local_name(paragraph.tag) != "p":
                continue

            paragraph_fragments = []
            for node in paragraph.iter():
                node_name = WordExtractionService._local_name(node.tag)
                if node_name == "t" and node.text:
                    paragraph_fragments.append(node.text)
                elif node_name in {"tab", "br", "cr"}:
                    paragraph_fragments.append(" ")

            paragraph_text = "".join(paragraph_fragments).strip()
            if paragraph_text:
                lines.append(paragraph_text)

        return {"content": [{"page": 1, "text": lines}]}

    @staticmethod
    def _extract_doc_to_json(file_path: str):
        try:
            if olefile is None:
                raise ValueError(WORD_CORRUPT_ERROR)

            with olefile.OleFileIO(file_path) as ole:
                if not ole.exists("WordDocument"):
                    raise ValueError(WORD_CORRUPT_ERROR)

                lines = []
                seen = set()
                for stream_name in ("WordDocument", "1Table", "0Table", "Data"):
                    if not ole.exists(stream_name):
                        continue
                    stream_bytes = ole.openstream(stream_name).read()
                    for line in WordExtractionService._extract_printable_lines(
                        stream_bytes
                    ):
                        if line in seen:
                            continue
                        seen.add(line)
                        lines.append(line)

                if not lines:
                    raise ValueError(DOC_UNREADABLE_TEXT_ERROR)
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(WORD_CORRUPT_ERROR) from exc

        return {"content": [{"page": 1, "text": lines}]}

    @staticmethod
    def _extract_printable_lines(payload: bytes) -> list[str]:
        lines = []
        encodings = ("utf-16-le", "utf-8", "cp1252", "latin-1")

        for encoding in encodings:
            decoded = payload.decode(encoding, errors="ignore")
            cleaned = re.sub(r"[^\x20-\x7E\n\r\t]", " ", decoded)
            for row in re.split(r"\r\n|\n|\r", cleaned):
                line = re.sub(r"\s+", " ", row).strip()
                if len(line) < 3:
                    continue
                if not re.search(r"[A-Za-z]", line):
                    continue

                alpha = len(re.findall(r"[A-Za-z]", line))
                density = alpha / max(len(line.replace(" ", "")), 1)
                if density < 0.35:
                    continue

                lines.append(line)

        return lines

    @staticmethod
    def _local_name(tag_name: str) -> str:
        if "}" in tag_name:
            return tag_name.rsplit("}", 1)[1]
        return tag_name
