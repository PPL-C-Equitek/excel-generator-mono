import os
import re
import zipfile
import xml.etree.ElementTree as ET


class WordExtractionService:
    """Extract text content from .doc and .docx into unified JSON format."""

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
            root = ET.fromstring(xml_bytes)
        except Exception as exc:
            raise ValueError(
                "Word file is corrupt or has an invalid structure."
            ) from exc

        lines = []
        for paragraph in root.iter():
            if WordExtractionService._local_name(paragraph.tag) != "p":
                continue

            fragments = []
            for node in paragraph.iter():
                node_name = WordExtractionService._local_name(node.tag)
                if node_name == "t" and node.text:
                    fragments.append(node.text)
                elif node_name in {"tab", "br", "cr"}:
                    fragments.append(" ")

            text = "".join(fragments).strip()
            if text:
                lines.append(text)

        return {"content": [{"page": 1, "text": lines}]}

    @staticmethod
    def _extract_doc_to_json(file_path: str):
        try:
            with open(file_path, "rb") as word_file:
                payload = word_file.read()
        except Exception as exc:
            raise ValueError(
                "Word file is corrupt or has an invalid structure."
            ) from exc

        candidates = [
            payload.decode("utf-16-le", errors="ignore"),
            payload.decode("latin-1", errors="ignore"),
        ]

        lines = []
        seen = set()
        for candidate in candidates:
            cleaned = re.sub(r"[^\x20-\x7E\n\r\t]", " ", candidate)
            for row in re.split(r"\r\n|\n|\r", cleaned):
                line = re.sub(r"\s+", " ", row).strip()
                if len(line) < 3:
                    continue
                if not re.search(r"[A-Za-z]", line):
                    continue
                if line in seen:
                    continue
                seen.add(line)
                lines.append(line)

        return {"content": [{"page": 1, "text": lines}]}

    @staticmethod
    def _local_name(tag_name: str) -> str:
        if "}" in tag_name:
            return tag_name.rsplit("}", 1)[1]
        return tag_name
