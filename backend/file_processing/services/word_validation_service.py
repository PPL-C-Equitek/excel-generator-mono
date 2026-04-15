import zipfile
import math
import xml.etree.ElementTree as ET
from io import BytesIO
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from docx import Document

EXT_DOCX = ".docx"
EXT_DOC = ".doc"
MAX_WORD_PAGES = 100
DOCX_CHARS_PER_PAGE_ESTIMATE = 2500
DOCX_WORDS_PER_PAGE_ESTIMATE = 350
DOCX_BLOCKS_PER_PAGE_ESTIMATE = 35
WORD_CORRUPT_ERROR = "Word file is corrupt or has an invalid structure."
WORD_PROTECTED_ERROR = "Word file is password-protected."
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


@dataclass
class WordValidationContext:
    uploaded_file: Any
    ext: str
    page_count: int = 0


class WordValidationHandler:
    def __init__(self, next_handler: Optional["WordValidationHandler"] = None):
        self._next_handler = next_handler

    def set_next(
        self, next_handler: "WordValidationHandler"
    ) -> "WordValidationHandler":
        self._next_handler = next_handler
        return next_handler

    def _next(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        if self._next_handler is None:
            return True, None
        return self._next_handler.handle(context)

    def handle(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError


class DocxEncryptedValidationHandler(WordValidationHandler):
    def handle(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        # Encrypted OOXML files are wrapped in OLE container, not regular ZIP-based DOCX.
        if is_ole_container(context.uploaded_file):
            return False, WORD_PROTECTED_ERROR
        return self._next(context)


class DocxStructureValidationHandler(WordValidationHandler):
    def handle(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        try:
            context.uploaded_file.seek(0)
            docx_bytes = context.uploaded_file.read()
            with zipfile.ZipFile(BytesIO(docx_bytes)) as archive:
                names = set(archive.namelist())
                if (
                    "[Content_Types].xml" not in names
                    or "word/document.xml" not in names
                ):
                    return False, WORD_CORRUPT_ERROR

                context.page_count = extract_docx_page_count(archive, docx_bytes)
        except Exception:
            return False, WORD_CORRUPT_ERROR
        finally:
            context.uploaded_file.seek(0)

        return self._next(context)


class DocEncryptedValidationHandler(WordValidationHandler):
    def handle(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        if not is_ole_container(context.uploaded_file):
            return False, WORD_CORRUPT_ERROR

        try:
            context.uploaded_file.seek(0)
            head = context.uploaded_file.read(4096)
            context.uploaded_file.seek(0)
            if b"EncryptedPackage" in head or b"EncryptionInfo" in head:
                return False, WORD_PROTECTED_ERROR
        except Exception:
            return False, WORD_CORRUPT_ERROR

        return self._next(context)


class DocStructureValidationHandler(WordValidationHandler):
    def handle(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        if not is_ole_container(context.uploaded_file):
            return False, WORD_CORRUPT_ERROR

        try:
            context.uploaded_file.seek(0)
            content = context.uploaded_file.read(1024 * 1024)
            context.uploaded_file.seek(0)

            if b"WordDocument" not in content:
                return False, WORD_CORRUPT_ERROR

            context.page_count = estimate_doc_page_count(content)
        except Exception:
            return False, WORD_CORRUPT_ERROR

        return self._next(context)


class WordPageCountValidationHandler(WordValidationHandler):
    def handle(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        if context.page_count > MAX_WORD_PAGES:
            return (
                False,
                f"Word exceeds the maximum allowed page count of {MAX_WORD_PAGES}.",
            )
        return True, None


def _build_word_validation_chain(ext: str) -> Optional[WordValidationHandler]:
    if ext == EXT_DOCX:
        start = DocxEncryptedValidationHandler()
        start.set_next(DocxStructureValidationHandler()).set_next(
            WordPageCountValidationHandler()
        )
        return start

    if ext == EXT_DOC:
        start = DocEncryptedValidationHandler()
        start.set_next(DocStructureValidationHandler()).set_next(
            WordPageCountValidationHandler()
        )
        return start

    return None


def validate_word(uploaded_file: Any, ext: str) -> Tuple[bool, Optional[str]]:
    chain = _build_word_validation_chain(ext)
    if chain is None:
        return False, "Unsupported file type."

    context = WordValidationContext(uploaded_file=uploaded_file, ext=ext)
    return chain.handle(context)


def check_docx_encrypted(uploaded_file: Any) -> Tuple[bool, Optional[str]]:
    # Encrypted OOXML files are wrapped in OLE container, not regular ZIP-based DOCX.
    if is_ole_container(uploaded_file):
        return False, WORD_PROTECTED_ERROR
    return True, None


def check_docx_structure(uploaded_file: Any) -> Tuple[bool, Any]:
    try:
        uploaded_file.seek(0)
        docx_bytes = uploaded_file.read()
        with zipfile.ZipFile(BytesIO(docx_bytes)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                return False, WORD_CORRUPT_ERROR

            page_count = extract_docx_page_count(archive, docx_bytes)
            return True, page_count
    except Exception:
        return False, WORD_CORRUPT_ERROR
    finally:
        uploaded_file.seek(0)


def extract_docx_page_count(archive: zipfile.ZipFile, docx_bytes: Optional[bytes] = None) -> int:
    app_pages = 0
    try:
        app_xml = archive.read("docProps/app.xml")
        root = ET.fromstring(app_xml)
        for element in root.iter():
            if element.tag.endswith("Pages") and element.text:
                app_pages = max(int(element.text), 0)
                if app_pages > 0:
                    break
    except Exception:
        pass

    try:
        document_xml = archive.read("word/document.xml")
    except Exception:
        return app_pages

    estimated_pages = _estimate_docx_pages_from_document_xml(document_xml)
    python_docx_pages = _estimate_docx_pages_with_python_docx(docx_bytes)
    return max(app_pages, estimated_pages, python_docx_pages)


def _estimate_docx_pages_with_python_docx(docx_bytes: Optional[bytes]) -> int:
    if not docx_bytes:
        return 0

    try:
        document = Document(BytesIO(docx_bytes))
    except Exception:
        return 0

    paragraph_count = 0
    table_row_count = 0
    word_count = 0
    explicit_page_breaks = 0

    for paragraph in document.paragraphs:
        paragraph_count += 1
        paragraph_text = paragraph.text.strip()
        if paragraph_text:
            word_count += len(paragraph_text.split())

        for node in paragraph._p.iter():
            node_name = _local_name(node.tag)
            if node_name == "lastRenderedPageBreak":
                explicit_page_breaks += 1
            elif node_name == "br":
                break_type = ""
                for key, value in node.attrib.items():
                    if key.endswith("type"):
                        break_type = (value or "").strip().lower()
                        break
                if break_type == "page":
                    explicit_page_breaks += 1

    for table in document.tables:
        for row in table.rows:
            table_row_count += 1
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    word_count += len(cell_text.split())

    break_estimate = explicit_page_breaks + 1 if explicit_page_breaks > 0 else 0

    section_estimate = 0
    try:
        if len(document.sections) > 1:
            section_estimate = len(document.sections)
    except Exception:
        section_estimate = 0

    word_estimate = 0
    if word_count > 0:
        word_estimate = max(1, math.ceil(word_count / DOCX_WORDS_PER_PAGE_ESTIMATE))

    structure_estimate = 0
    block_count = paragraph_count + table_row_count
    if block_count > 0:
        structure_estimate = max(
            1, math.ceil(block_count / DOCX_BLOCKS_PER_PAGE_ESTIMATE)
        )

    return max(break_estimate, section_estimate, word_estimate, structure_estimate)


def _estimate_docx_pages_from_document_xml(document_xml: bytes) -> int:
    try:
        root = ET.fromstring(document_xml)
    except Exception:
        return 0

    if _local_name(root.tag) != "document":
        return 0

    manual_page_breaks = 0
    rendered_page_breaks = 0
    page_break_before_count = 0
    section_count = 0
    text_char_count = 0

    for node in root.iter():
        node_name = _local_name(node.tag)

        if node_name == "lastRenderedPageBreak":
            rendered_page_breaks += 1
        elif node_name == "br":
            break_type = ""
            for key, value in node.attrib.items():
                if key.endswith("type"):
                    break_type = (value or "").strip().lower()
                    break
            if break_type == "page":
                manual_page_breaks += 1
        elif node_name == "pageBreakBefore":
            page_break_before_count += 1
        elif node_name == "sectPr":
            section_count += 1
        elif node_name == "t" and node.text:
            text_char_count += len(node.text.strip())

    marker_estimate = 0
    if rendered_page_breaks > 0:
        marker_estimate = max(marker_estimate, rendered_page_breaks + 1)
    if manual_page_breaks > 0:
        marker_estimate = max(marker_estimate, manual_page_breaks + 1)
    if page_break_before_count > 0:
        marker_estimate = max(marker_estimate, page_break_before_count + 1)
    if section_count > 1:
        marker_estimate = max(marker_estimate, section_count)

    text_estimate = 0
    if text_char_count > 0:
        text_estimate = max(1, math.ceil(text_char_count / DOCX_CHARS_PER_PAGE_ESTIMATE))

    return max(marker_estimate, text_estimate)


def _local_name(tag_name: str) -> str:
    if "}" in tag_name:
        return tag_name.rsplit("}", 1)[1]
    return tag_name


def check_doc_encrypted(uploaded_file: Any) -> Tuple[bool, Optional[str]]:
    if not is_ole_container(uploaded_file):
        return False, WORD_CORRUPT_ERROR

    try:
        uploaded_file.seek(0)
        head = uploaded_file.read(4096)
        uploaded_file.seek(0)
        if b"EncryptedPackage" in head or b"EncryptionInfo" in head:
            return False, WORD_PROTECTED_ERROR
    except Exception:
        return False, WORD_CORRUPT_ERROR

    return True, None


def check_doc_structure(uploaded_file: Any) -> Tuple[bool, Any]:
    if not is_ole_container(uploaded_file):
        return False, WORD_CORRUPT_ERROR

    try:
        uploaded_file.seek(0)
        content = uploaded_file.read(1024 * 1024)
        uploaded_file.seek(0)

        if b"WordDocument" not in content:
            return False, WORD_CORRUPT_ERROR

        return True, estimate_doc_page_count(content)
    except Exception:
        return False, WORD_CORRUPT_ERROR


def estimate_doc_page_count(content: bytes) -> int:
    """Best-effort page estimation for binary .doc content.

    Legacy .doc does not expose page count cheaply without full OLE parsing,
    so we estimate from page-break markers to make max-page checks enforceable.
    """
    if not content:
        return 0

    marker_count = content.count(b"\x0c")

    try:
        utf16_text = content.decode("utf-16-le", errors="ignore")
        marker_count = max(marker_count, utf16_text.count("\x0c"))
    except Exception:
        pass

    try:
        latin_text = content.decode("latin-1", errors="ignore")
        marker_count = max(marker_count, latin_text.count("\x0c"))
    except Exception:
        pass

    if marker_count <= 0:
        return 0

    return marker_count + 1


def check_word_page_count(page_count: int) -> Tuple[bool, Optional[str]]:
    if page_count > MAX_WORD_PAGES:
        return (
            False,
            f"Word exceeds the maximum allowed page count of {MAX_WORD_PAGES}.",
        )
    return True, None


def is_ole_container(uploaded_file: Any) -> bool:
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(len(OLE_SIGNATURE))
        uploaded_file.seek(0)
        return header == OLE_SIGNATURE
    except Exception:
        return False
