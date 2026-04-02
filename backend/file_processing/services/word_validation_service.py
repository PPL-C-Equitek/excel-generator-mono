import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Optional, Tuple

EXT_DOCX = ".docx"
EXT_DOC = ".doc"
MAX_WORD_PAGES = 100
WORD_CORRUPT_ERROR = "Word file is corrupt or has an invalid structure."
OLE_SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


@dataclass
class WordValidationContext:
    uploaded_file: Any
    ext: str
    page_count: int = 0


class WordValidationHandler:
    def __init__(self, next_handler: Optional["WordValidationHandler"] = None):
        self._next_handler = next_handler

    def set_next(self, next_handler: "WordValidationHandler") -> "WordValidationHandler":
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
            return False, "Word file is password-protected."
        return self._next(context)


class DocxStructureValidationHandler(WordValidationHandler):
    def handle(self, context: WordValidationContext) -> Tuple[bool, Optional[str]]:
        try:
            context.uploaded_file.seek(0)
            with zipfile.ZipFile(context.uploaded_file) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    return False, WORD_CORRUPT_ERROR

                context.page_count = extract_docx_page_count(archive)
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
                return False, "Word file is password-protected."
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

            context.page_count = 0
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
        return False, "Word file is password-protected."
    return True, None


def check_docx_structure(uploaded_file: Any) -> Tuple[bool, Any]:
    try:
        uploaded_file.seek(0)
        with zipfile.ZipFile(uploaded_file) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                return False, WORD_CORRUPT_ERROR

            page_count = extract_docx_page_count(archive)
            return True, page_count
    except Exception:
        return False, WORD_CORRUPT_ERROR
    finally:
        uploaded_file.seek(0)


def extract_docx_page_count(archive: zipfile.ZipFile) -> int:
    try:
        app_xml = archive.read("docProps/app.xml")
        root = ET.fromstring(app_xml)
        for element in root.iter():
            if element.tag.endswith("Pages") and element.text:
                return max(int(element.text), 0)
    except Exception:
        return 0

    return 0


def check_doc_encrypted(uploaded_file: Any) -> Tuple[bool, Optional[str]]:
    if not is_ole_container(uploaded_file):
        return False, WORD_CORRUPT_ERROR

    try:
        uploaded_file.seek(0)
        head = uploaded_file.read(4096)
        uploaded_file.seek(0)
        if b"EncryptedPackage" in head or b"EncryptionInfo" in head:
            return False, "Word file is password-protected."
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

        return True, 0
    except Exception:
        return False, WORD_CORRUPT_ERROR


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
