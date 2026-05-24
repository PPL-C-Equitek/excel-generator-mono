"""Conservative OCR cleanup helpers.

This module normalizes OCR output without adding another model call. It keeps
the OCR pipeline deterministic:
- preserve layout structure when word-level data is available
- only correct high-confidence tokens
- preserve schema/domain terminology and numeric patterns
- expose confidence metadata for downstream prompt injection and validation
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import get_close_matches
from statistics import mean
from typing import Any, Iterable

try:  # Optional dependency; pipeline still works without it.
    from spellchecker import SpellChecker
except Exception:  # pragma: no cover - optional dependency
    SpellChecker = None

logger = logging.getLogger(__name__)

_HIGH_CONFIDENCE_THRESHOLD = 75.0
_LOW_CONFIDENCE_THRESHOLD = 60.0
_LOW_CONFIDENCE_REGION_THRESHOLD = 40.0

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]+|\s+")
_WORD_PATTERN = re.compile(r"^[A-Za-z][A-Za-z'\-]*$")
_NUMERIC_PATTERN = re.compile(r"^[\d,.$%()+\-/:]+$")
_SPECIAL_TERMS_PATTERN = re.compile(r"[_@#]")

_FALLBACK_DOMAIN_TERMS = {
    "amount",
    "api",
    "balance",
    "cell",
    "column",
    "cost",
    "credit",
    "csv",
    "debit",
    "document",
    "ean",
    "excel",
    "expense",
    "footer",
    "formula",
    "header",
    "http",
    "income",
    "invoice",
    "json",
    "item",
    "line",
    "ocr",
    "payment",
    "pivot",
    "price",
    "qty",
    "regex",
    "receipt",
    "revenue",
    "row",
    "sheet",
    "sku",
    "sql",
    "subtotal",
    "summary",
    "table",
    "total",
    "unit",
    "usd",
    "workbook",
    "xml",
    "yaml",
}


@dataclass(frozen=True)
class OCRConfidenceRegion:
    start_pos: int
    end_pos: int
    confidence_level: str
    avg_confidence: float
    text_content: str


def _flatten_terms(value: Any) -> set[str]:
    terms: set[str] = set()
    if value is None:
        return terms
    if isinstance(value, str):
        for chunk in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-/.]*", value):
            normalized = chunk.strip().lower()
            if normalized:
                terms.add(normalized)
        return terms
    if isinstance(value, dict):
        for item in value.values():
            terms.update(_flatten_terms(item))
        return terms
    if isinstance(value, (list, tuple, set)):
        for item in value:
            terms.update(_flatten_terms(item))
    return terms


def _case_preserving_replace(original: str, corrected: str) -> str:
    if original.isupper():
        return corrected.upper()
    if original[:1].isupper():
        return corrected.capitalize()
    return corrected


def _is_preservable_token(token: str) -> bool:
    if not token or token.isspace():
        return True
    if _NUMERIC_PATTERN.fullmatch(token):
        return True
    if _SPECIAL_TERMS_PATTERN.search(token):
        return True
    if any(character.isdigit() for character in token):
        return True
    if token.isupper() and len(token) <= 6:
        return True
    return False


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text)


def _token_confidence_level(confidence: float) -> str:
    if confidence >= _HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if confidence >= _LOW_CONFIDENCE_REGION_THRESHOLD:
        return "medium"
    return "low"


def _word_confidence(detail: dict[str, Any]) -> float:
    confidence = detail.get("confidence", detail.get("conf", 0.0))
    if isinstance(confidence, (int, float)):
        return max(0.0, float(confidence))
    return 0.0


class OCRCleanupService:
    def __init__(self, spell_checker: Any | None = None):
        self.spell_checker = spell_checker if spell_checker is not None else self._build_spell_checker()

    @staticmethod
    def _build_spell_checker() -> Any | None:
        if SpellChecker is None:
            return None
        try:
            return SpellChecker(language="en")
        except Exception:  # pragma: no cover - optional dependency/setup issues
            logger.debug("Spell checker initialisation failed.", exc_info=True)
            return None

    @staticmethod
    def _remove_space_before_punct(text: str) -> str:
        """Remove whitespace immediately preceding punctuation characters.

        This is implemented with a linear-time scan to avoid any chance of
        catastrophic backtracking from complex regular expressions.
        """
        if not text:
            return text
        punct = {",", ".", ";", ":", "!", "?"}
        out: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch.isspace():
                # look ahead to the next non-space character
                j = i
                while j < n and text[j].isspace():
                    j += 1
                if j < n and text[j] in punct:
                    # skip all whitespace that precedes punctuation
                    i = j
                    continue
                # not before punctuation: preserve the original whitespace sequence
                out.append(ch)
                i += 1
            else:
                out.append(ch)
                i += 1
        return "".join(out)

    @staticmethod
    def _extract_candidate_terms(schema_definitions: Any | None) -> set[str]:
        terms = set(_FALLBACK_DOMAIN_TERMS)
        terms.update(_flatten_terms(schema_definitions))
        return terms

    def _spellchecker_candidate(self, lookup: str) -> str | None:
        spell_checker = self.spell_checker
        if spell_checker is None:
            return None

        try:
            if hasattr(spell_checker, "known") and spell_checker.known([lookup]):
                return lookup
            return spell_checker.correction(lookup)
        except Exception:  # pragma: no cover - optional dependency edge cases
            return None

    @staticmethod
    def _fallback_candidate(lookup: str, domain_terms: set[str]) -> str | None:
        fallback_candidates = sorted(domain_terms)
        matches = get_close_matches(lookup, fallback_candidates, n=1, cutoff=0.9)
        return matches[0] if matches else None

    def _correct_token(self, token: str, domain_terms: set[str]) -> tuple[str, str | None]:
        normalized = token.strip()
        if not normalized:
            return token, None

        lookup = normalized.lower()
        if lookup in domain_terms or _is_preservable_token(normalized):
            return token, None
        if not _WORD_PATTERN.fullmatch(normalized):
            return token, None

        candidate = self._spellchecker_candidate(lookup)
        if not candidate or candidate == lookup:
            candidate = self._fallback_candidate(lookup, domain_terms)

        if not candidate or candidate == lookup:
            return token, None

        corrected = _case_preserving_replace(normalized, candidate)
        return corrected, f"{token}->{corrected}"

    def _clean_line(
        self,
        line_text: str,
        line_confidence: float,
        domain_terms: set[str],
    ) -> tuple[str, list[str]]:
        if line_confidence < _HIGH_CONFIDENCE_THRESHOLD:
            return line_text.strip(), []

        corrections: list[str] = []
        cleaned_tokens: list[str] = []
        for token in _tokenize(line_text):
            if token.isspace() or not token.strip():
                continue

            stripped = token.strip()
            corrected, correction = self._correct_token(stripped, domain_terms)
            cleaned_tokens.append(corrected)
            if correction:
                corrections.append(correction)

        cleaned_line = " ".join(cleaned_tokens).strip()
        cleaned_line = self._remove_space_before_punct(cleaned_line)
        return cleaned_line, corrections

    def _clean_word(self, word: str, confidence: float, domain_terms: set[str]) -> tuple[str, str | None]:
        if confidence < _HIGH_CONFIDENCE_THRESHOLD:
            return word, None
        return self._correct_token(word, domain_terms)

    def _cleanup_with_word_details(
        self,
        normalized_word_details: list[dict[str, Any]],
        avg_confidence: float,
        domain_terms: set[str],
    ) -> dict[str, Any]:
        lines: list[dict[str, Any]] = []
        applied_corrections: list[str] = []
        grouped_lines = self._group_word_details(normalized_word_details)
        regions: list[OCRConfidenceRegion] = []
        cursor = 0

        for line_index, line_words in enumerate(grouped_lines):
            ordered_words = [
                str(word.get("text", "")).strip()
                for word in line_words
                if str(word.get("text", "")).strip()
            ]
            if not ordered_words:
                continue

            cleaned_words: list[str] = []
            line_confidences: list[float] = []
            for word in line_words:
                raw_word = str(word.get("text", "")).strip()
                if not raw_word:
                    continue

                confidence = _word_confidence(word)
                line_confidences.append(confidence)
                cleaned_word, correction = self._clean_word(raw_word, confidence, domain_terms)
                cleaned_words.append(cleaned_word)
                if correction:
                    applied_corrections.append(correction)

                start_pos = cursor
                end_pos = start_pos + len(cleaned_word)
                regions.append(
                    OCRConfidenceRegion(
                        start_pos=start_pos,
                        end_pos=end_pos,
                        confidence_level=_token_confidence_level(confidence),
                        avg_confidence=round(float(confidence), 2),
                        text_content=cleaned_word,
                    )
                )
                cursor = end_pos + 1

            line_confidence = mean(line_confidences) if line_confidences else 0.0
            cleaned_line = " ".join(cleaned_words).strip()
            # Normalize spacing before punctuation (e.g. turn "Amount : 100" into "Amount: 100").
            cleaned_line = self._remove_space_before_punct(cleaned_line)
            lines.append({
                "text": cleaned_line,
                "avg_confidence": round(float(line_confidence), 2),
            })

            if line_index < len(grouped_lines) - 1:
                cursor += 1

        cleaned_text = "\n".join(line["text"] for line in lines if line["text"])
        confidence_score = self._aggregate_confidence(regions, avg_confidence)
        serialized_regions = self._serialize_regions(regions)
        low_confidence_regions = self._build_low_confidence_regions(serialized_regions)
        return {
            "text": cleaned_text,
            "avg_confidence": confidence_score,
            "regions": serialized_regions,
            "corrections_applied": applied_corrections,
            "confidence_score": confidence_score,
            "confidence_level": self._confidence_level_from_score(confidence_score),
            "correction_count": len(applied_corrections),
            "low_confidence_regions": low_confidence_regions,
            "processing_method": "tesseract_multi_psm_layout_aware",
        }

    def _cleanup_without_word_details(
        self,
        text: str,
        avg_confidence: float,
        domain_terms: set[str],
    ) -> dict[str, Any]:
        cleaned_lines: list[dict[str, Any]] = []
        applied_corrections: list[str] = []

        for raw_line in [line.strip() for line in text.splitlines() if line.strip()]:
            line_confidence = avg_confidence
            cleaned_line, corrections = self._clean_line(raw_line, line_confidence, domain_terms)
            cleaned_lines.append({
                "text": cleaned_line,
                "avg_confidence": round(float(line_confidence), 2),
            })
            applied_corrections.extend(corrections)

        if not cleaned_lines and text.strip():
            cleaned_lines.append({
                "text": text.strip(),
                "avg_confidence": round(float(avg_confidence), 2),
            })

        regions = self._build_regions(cleaned_lines)
        cleaned_text = "\n".join(line["text"] for line in cleaned_lines if line["text"])
        confidence_score = self._aggregate_confidence(regions, avg_confidence)
        serialized_regions = self._serialize_regions(regions)
        low_confidence_regions = self._build_low_confidence_regions(serialized_regions)
        return {
            "text": cleaned_text,
            "avg_confidence": confidence_score,
            "regions": serialized_regions,
            "corrections_applied": applied_corrections,
            "confidence_score": confidence_score,
            "confidence_level": self._confidence_level_from_score(confidence_score),
            "correction_count": len(applied_corrections),
            "low_confidence_regions": low_confidence_regions,
            "processing_method": "tesseract_line_cleanup",
        }

    @staticmethod
    def _group_word_details(word_details: Iterable[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        grouped: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
        for index, detail in enumerate(word_details):
            block_num = int(detail.get("block_num", 0) or 0)
            par_num = int(detail.get("par_num", 0) or 0)
            line_num = int(detail.get("line_num", 0) or 0)
            grouped.setdefault((block_num, par_num, line_num), []).append(
                {
                    **detail,
                    "_index": index,
                }
            )

        ordered_lines: list[list[dict[str, Any]]] = []
        for key in sorted(grouped.keys()):
            line_words = sorted(
                grouped[key],
                key=lambda item: (int(item.get("left", 0) or 0), int(item.get("_index", 0) or 0)),
            )
            ordered_lines.append(line_words)
        return ordered_lines

    @staticmethod
    def _build_regions(lines: list[dict[str, Any]]) -> list[OCRConfidenceRegion]:
        regions: list[OCRConfidenceRegion] = []
        cursor = 0
        for line in lines:
            text = line["text"]
            avg_confidence = line["avg_confidence"]
            start_pos = cursor
            end_pos = start_pos + len(text)
            regions.append(
                OCRConfidenceRegion(
                    start_pos=start_pos,
                    end_pos=end_pos,
                    confidence_level=_token_confidence_level(avg_confidence),
                    avg_confidence=avg_confidence,
                    text_content=text,
                )
            )
            cursor = end_pos + 1
        return regions

    @staticmethod
    def _aggregate_confidence(regions: list[OCRConfidenceRegion], fallback: float) -> float:
        if regions:
            return round(mean(region.avg_confidence for region in regions), 2)
        return round(float(fallback), 2)

    @staticmethod
    def _serialize_regions(regions: list[OCRConfidenceRegion]) -> list[dict[str, Any]]:
        return [
            {
                "start_pos": region.start_pos,
                "end_pos": region.end_pos,
                "confidence_level": region.confidence_level,
                "avg_confidence": round(region.avg_confidence, 2),
                "text_content": region.text_content,
            }
            for region in regions
        ]

    @staticmethod
    def _confidence_level_from_score(score: float) -> str:
        if score >= _HIGH_CONFIDENCE_THRESHOLD:
            return "high"
        if score >= _LOW_CONFIDENCE_THRESHOLD:
            return "medium"
        return "low"

    @staticmethod
    def _build_low_confidence_regions(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "text": region["text_content"],
                "confidence": round(region["avg_confidence"], 2),
                "position": region["start_pos"],
            }
            for region in regions
            if region["avg_confidence"] < _LOW_CONFIDENCE_THRESHOLD
        ][:5]

    @classmethod
    def summarize_page_metadata(
        cls,
        page_metadata: list[dict[str, Any]],
        document_type: str,
    ) -> dict[str, Any]:
        confidences = [
            float(page.get("confidence_score", 0.0))
            for page in page_metadata
            if isinstance(page, dict)
        ]
        corrections: list[str] = []
        low_confidence_regions: list[dict[str, Any]] = []
        for page in page_metadata:
            if not isinstance(page, dict):
                continue
            corrections.extend(page.get("corrections_applied", []))
            low_confidence_regions.extend(page.get("low_confidence_regions", []))

        confidence_score = round(mean(confidences), 2) if confidences else 0.0
        confidence_level = cls._confidence_level_from_score(confidence_score)
        return {
            "document_type": document_type,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "correction_count": len(corrections),
            "corrections_applied": corrections,
            "low_confidence_regions": low_confidence_regions[:5],
            "processing_method": "tesseract_multi_psm_layout_aware",
        }

    def cleanup_text(
        self,
        text: str,
        avg_confidence: float = 0.0,
        word_details: Iterable[dict[str, Any]] | None = None,
        schema_definitions: Any | None = None,
        document_type: str = "unknown",
    ) -> dict[str, Any]:
        domain_terms = self._extract_candidate_terms(schema_definitions)
        normalized_word_details = [dict(detail) for detail in word_details or [] if isinstance(detail, dict)]

        if normalized_word_details:
            cleanup_result = self._cleanup_with_word_details(
                normalized_word_details=normalized_word_details,
                avg_confidence=avg_confidence,
                domain_terms=domain_terms,
            )
        else:
            cleanup_result = self._cleanup_without_word_details(
                text=text,
                avg_confidence=avg_confidence,
                domain_terms=domain_terms,
            )

        ocr_metadata = {
            "document_type": document_type,
            "confidence_score": cleanup_result["confidence_score"],
            "confidence_level": cleanup_result["confidence_level"],
            "correction_count": cleanup_result["correction_count"],
            "corrections_applied": cleanup_result["corrections_applied"],
            "low_confidence_regions": cleanup_result["low_confidence_regions"],
            "processing_method": cleanup_result["processing_method"],
        }

        return {
            "text": cleanup_result["text"],
            "avg_confidence": cleanup_result["avg_confidence"],
            "regions": cleanup_result["regions"],
            "corrections_applied": cleanup_result["corrections_applied"],
            "ocr_metadata": ocr_metadata,
        }