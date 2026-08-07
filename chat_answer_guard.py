from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


UNSUPPORTED_NOTE = "(not found in evidence)"

_YEAR_RE = re.compile(r"(?<![\d.])(?:20\d{2}|25\d{2})(?![\d.])")
_NUMBER_RE = re.compile(r"(?<![\d.])\d[\d,]*(?:\.\d+)?(?![\d.])")
_CITATION_RE = re.compile(r"\[web:(\d+)\]")
_THAI_MONTHS = (
    "ม.ค.",
    "ก.พ.",
    "มี.ค.",
    "เม.ย.",
    "พ.ค.",
    "มิ.ย.",
    "ก.ค.",
    "ส.ค.",
    "ก.ย.",
    "ต.ค.",
    "พ.ย.",
    "ธ.ค.",
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)
_EN_MONTHS = (
    "Jan",
    "January",
    "Feb",
    "February",
    "Mar",
    "March",
    "Apr",
    "April",
    "May",
    "Jun",
    "June",
    "Jul",
    "July",
    "Aug",
    "August",
    "Sep",
    "Sept",
    "September",
    "Oct",
    "October",
    "Nov",
    "November",
    "Dec",
    "December",
)
_MONTH_PATTERN = "|".join(re.escape(month) for month in (*_THAI_MONTHS, *_EN_MONTHS))
_PARTIAL_DATE_RE = re.compile(rf"\b(\d{{1,2}})\s*[- ]?\s*({_MONTH_PATTERN})\.?", re.IGNORECASE)
_VERSION_CONTEXT_RE = re.compile(r"(?:\bversion\b|\bv\.?\s*$|\bver\.?\s*$|รุ่น\s*$)", re.IGNORECASE)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    violations: list[str]
    corrected_answer: str | None


def validate_answer(
    answer: str,
    *,
    evidence_corpus: str,
    sources: list[dict],
    allow: tuple[str, ...] = (),
) -> GuardResult:
    answer_text = str(answer or "")
    evidence_text = str(evidence_corpus or "")
    allowed_values = tuple(str(value) for value in allow)
    if not evidence_text.strip():
        return GuardResult(ok=True, violations=[], corrected_answer=None)

    violations: list[str] = []
    unsupported_years: list[str] = []
    unsupported_numbers: list[str] = []

    evidence_numbers = _numeric_values(evidence_text)
    allowed_numbers = _numeric_values(" ".join(allowed_values))

    for match in _YEAR_RE.finditer(answer_text):
        year = match.group(0)
        if _is_allowed_literal(year, evidence_text, allowed_values):
            continue
        if _is_version_like(answer_text, match.start()):
            continue
        unsupported_years.append(year)
        violations.append(f"unsupported year: {year}")

    partial_date_violations = _partial_date_year_violations(
        answer_text,
        evidence_text,
        allowed_values,
    )
    for partial, year in partial_date_violations:
        violations.append(f"partial date gained unsupported year: {partial} {year}")
        if year not in unsupported_years:
            unsupported_years.append(year)

    for match in _NUMBER_RE.finditer(answer_text):
        token = match.group(0)
        if token in unsupported_years:
            continue
        if _is_allowed_number(token, allowed_numbers):
            continue
        if not _has_price_context(answer_text, match.start(), match.end()):
            continue
        value = _parse_number(token)
        if value is None or value in evidence_numbers:
            continue
        unsupported_numbers.append(token)
        violations.append(f"unsupported price/currency figure: {token}")

    if _has_suspicious_uniform_price_values(answer_text):
        violations.append("suspicious uniform price values across multiple rows")

    valid_indices = _source_indices(sources)
    for citation in _CITATION_RE.finditer(answer_text):
        index = int(citation.group(1))
        if index not in valid_indices:
            violations.append(f"dangling citation: [web:{index}]")

    corrected = _correct_answer(
        answer_text,
        unsupported_years=unsupported_years,
        unsupported_numbers=unsupported_numbers,
        violations=violations,
    )
    return GuardResult(ok=not violations, violations=violations, corrected_answer=corrected)


def _partial_date_year_violations(answer: str, evidence: str, allow: tuple[str, ...]) -> list[tuple[str, str]]:
    del allow
    evidence_partials = {
        _normalize_partial_date(match.group(1), match.group(2))
        for match in _PARTIAL_DATE_RE.finditer(evidence)
        if not _year_near(evidence, match.end())
    }
    if not evidence_partials:
        return []

    violations: list[tuple[str, str]] = []
    for match in _PARTIAL_DATE_RE.finditer(answer):
        partial = _normalize_partial_date(match.group(1), match.group(2))
        if partial not in evidence_partials:
            continue
        tail = answer[match.end() : match.end() + 16]
        year_match = _YEAR_RE.search(tail)
        if not year_match:
            continue
        year = year_match.group(0)
        if year in evidence:
            continue
        violations.append((partial, year))
    return violations


def _normalize_partial_date(day: str, month: str) -> str:
    return f"{int(day)} {month.strip()}"


def _year_near(text: str, offset: int) -> bool:
    return bool(_YEAR_RE.search(text[max(0, offset - 4) : offset + 16]))


def _source_indices(sources: list[dict]) -> set[int]:
    indices: set[int] = set()
    for source in sources:
        try:
            indices.add(int(source.get("index")))
        except (TypeError, ValueError):
            continue
    return indices


def _is_allowed_literal(value: str, evidence: str, allow: tuple[str, ...]) -> bool:
    return value in evidence or any(value in allowed for allowed in allow)


def _numeric_values(text: str) -> set[Decimal]:
    values: set[Decimal] = set()
    for match in _NUMBER_RE.finditer(text):
        value = _parse_number(match.group(0))
        if value is not None:
            values.add(value)
    return values


def _parse_number(value: str) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "")).normalize()
    except (InvalidOperation, ValueError):
        return None


def _is_allowed_number(token: str, allowed_numbers: set[Decimal]) -> bool:
    value = _parse_number(token)
    return value is not None and value in allowed_numbers


def _is_version_like(answer: str, year_start: int) -> bool:
    prefix = answer[max(0, year_start - 18) : year_start]
    return bool(_VERSION_CONTEXT_RE.search(prefix))


def _has_price_context(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 8) : start].lower()
    after = text[end : end + 18].lower()
    return (
        any(marker in before for marker in ("฿", "$", "thb", "usd"))
        or any(
            marker in after
            for marker in (
                "บาท",
                "฿",
                "$",
                "thb",
                "usd",
                "baht",
                "/ลิตร",
                "ต่อลิตร",
                "per liter",
                "per litre",
            )
        )
    )


def _has_suspicious_uniform_price_values(text: str) -> bool:
    values: list[Decimal] = []
    for match in _NUMBER_RE.finditer(text):
        if not _has_price_value_context(text, match.start(), match.end()):
            continue
        value = _parse_number(match.group(0))
        if value is not None:
            values.append(value)
    return len(values) >= 3 and len(set(values)) == 1


def _has_price_value_context(text: str, start: int, end: int) -> bool:
    after = text[end : end + 18].lower().lstrip()
    return any(
        after.startswith(marker)
        for marker in (
            "บาท",
            "/ลิตร",
            "ลิตร",
            "$",
            "thb",
            "usd",
            "baht",
            "per liter",
            "per litre",
        )
    )

def _correct_answer(
    answer: str,
    *,
    unsupported_years: list[str],
    unsupported_numbers: list[str],
    violations: list[str],
) -> str | None:
    if not violations:
        return None

    corrected = answer
    for year in dict.fromkeys(unsupported_years):
        corrected = re.sub(rf"(?<![\d.]){re.escape(year)}(?![\d.])", "", corrected)
    for number in dict.fromkeys(unsupported_numbers):
        corrected = re.sub(
            rf"(?<![\d.]){re.escape(number)}(?![\d.])",
            f"{number} {UNSUPPORTED_NOTE}",
            corrected,
            count=1,
        )
    corrected = _cleanup_spaces(corrected)
    if corrected == answer:
        corrected = f"{answer}\n\nGuard notes: {'; '.join(violations)}"
    return corrected


def _cleanup_spaces(value: str) -> str:
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\s+([.,;:!?])", r"\1", value)
    return value.strip()
