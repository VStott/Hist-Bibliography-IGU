import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from citeproc import Citation, CitationItem, CitationStylesBibliography, CitationStylesStyle, formatter
from citeproc.source.json import CiteProcJSON

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSL_PATH = os.path.join(BASE_DIR, "hist_IGU_gost-r-7-0-5-2008-numeric-alphabetical.csl")

LOCALE_MAP = {
    "ru": "ru-RU",
    "en": "en-US",
    "fr": "fr-FR",
    "de": "de-DE",
}

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_NAME_PARTICLES = {"de", "du", "des", "la", "le", "les", "d'", "von", "van", "der", "den", "del", "di", "da"}


@lru_cache(maxsize=16)
def _load_style(style_path: str, locale: str) -> CitationStylesStyle:
    """Кэшируем для экономии"""
    if not os.path.exists(style_path):
        raise FileNotFoundError(f"Файл стиля CSL не найден по пути: {style_path}")
    return CitationStylesStyle(style_path, locale=locale, validate=False)


def _resolve_locale(item: Dict[str, Any]) -> str:
    """Best Current Practice 47 по полю language"""
    lang = str(item.get("language", "ru")).lower().strip()
    if lang in LOCALE_MAP:
        return LOCALE_MAP[lang]
    short = lang.split("-")[0]
    return LOCALE_MAP.get(short, "ru-RU")


def _to_initials(given: str) -> str:
    """Нужно для частиц фамилий ('de', 'von') и дефисов как в двойных именах ('J.-Y.')."""
    tokens = given.strip().split()
    out: List[str] = []
    for tok in tokens:
        if tok.lower() in _NAME_PARTICLES:
            out.append(tok)
            continue
        if "-" in tok:
            subparts = [p for p in tok.split("-") if p]
            out.append("-".join(f"{p[0]}." for p in subparts))
        else:
            out.append(f"{tok[0]}.")
    return " ".join(out)


def format_head_author(authors: Optional[List[Dict[str, str]]]) -> Optional[str]:
    """1-3 автора: 1 автора в начале, 0 или 4 автора: None. Поправьте если я не правильно понял методичку"""
    if not authors or not isinstance(authors, list) or len(authors) > 3:
        return None

    first = authors[0]
    if not isinstance(first, dict):
        return None

    if first.get("literal"):
        lit = str(first["literal"]).strip()
        return lit if lit.endswith(".") else f"{lit}."

    family = str(first.get("family", "")).strip()
    given = str(first.get("given", "")).strip()
    if not family and not given:
        return None

    if family and given:
        return f"{family} {_to_initials(given)}"
    if family:
        return family if family.endswith(".") else f"{family}."
    return _to_initials(given)


def _cleanup_punctuation(text: str) -> str:
    """Всякие шероховатости удаляет - лучше не трогать этот раздел"""
    text = text.strip()
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    text = re.sub(r"([?!])\.\s+–", r"\1 –", text)
    text = re.sub(r" {2,}", " ", text)
    return text


def _ensure_dot(s: str) -> str:
    s = s.strip()
    return s if s.endswith(".") else f"{s}."


def render_archive_citation(csl_item: Dict[str, Any]) -> str:
    """Архивы"""
    arch = csl_item.get("archive_data") or {}
    name = (arch.get("archive_name") or csl_item.get("title") or "").strip()
    abbr = (arch.get("archive_abbr") or "").strip()
    if not name and not abbr:
        raise ValueError("Для архивного документа укажите название архива или его аббревиатуру.")

    parts: List[str] = []
    if name and abbr:
        parts.append(f"{name} ({abbr}).")
    elif name:
        parts.append(_ensure_dot(name))
    else:
        parts.append(_ensure_dot(abbr))

    if arch.get("fond"):
        parts.append(_ensure_dot(f"Ф. {arch['fond']}"))
    if arch.get("opis"):
        parts.append(_ensure_dot(f"Оп. {arch['opis']}"))
    if arch.get("sub_unit"):
        parts.append(_ensure_dot(arch["sub_unit"]))
    if arch.get("delo"):
        delo_type = (arch.get("delo_type") or "Д.").strip()
        if delo_type.startswith("№"):
            parts.append(_ensure_dot(f"№ {arch['delo']}"))
        else:
            parts.append(_ensure_dot(f"{delo_type} {arch['delo']}"))
    if arch.get("list_num"):
        parts.append(_ensure_dot(f"Л. {arch['list_num']}"))
    if arch.get("doc_title"):
        parts.append(_ensure_dot(arch["doc_title"]))

    return _cleanup_punctuation(" ".join(parts))


def _format_ru_date(date_obj: Optional[Dict[str, Any]]) -> Optional[str]:
    if not date_obj or "date-parts" not in date_obj:
        return None
    parts = date_obj["date-parts"][0]
    if len(parts) == 3:
        return f"{parts[2]:02d}.{parts[1]:02d}.{parts[0]:04d}"
    if len(parts) == 2:
        return f"{parts[1]:02d}.{parts[0]:04d}"
    if len(parts) == 1:
        return str(parts[0])
    return None


def render_legislation_citation(csl_item: Dict[str, Any]) -> str:
    leg = csl_item.get("legislation_data") or {}
    title = (leg.get("title") or csl_item.get("title") or "").strip()
    if not title:
        raise ValueError("Для нормативно-правового акта укажите название.")

    # Заглавная часть: Название : Вид/номер : [принят ...]
    header_parts = [title]
    law_desc = " ".join(x for x in [leg.get("law_type"), leg.get("law_number")] if x).strip()
    if law_desc:
        header_parts.append(law_desc)
    if leg.get("adoption_info"):
        info = leg["adoption_info"].strip()
        if not (info.startswith("[") and info.endswith("]")):
            info = f"[{info}]"
        header_parts.append(info)

    text = " : ".join(header_parts)

    url = leg.get("url")
    container = leg.get("container_title")

    # Если электронный акт из СПС/портала (Гарант, Консультант, НЭБ) без печатного сборника
    if url and container and not leg.get("publisher"):
        text += f". – Текст : электронный // {container}"
        if leg.get("year"):
            text += f". – {leg['year']}"
        accessed_str = _format_ru_date(leg.get("accessed_date"))
        url_block = f"URL: {url}" + (f" (дата обращения: {accessed_str})" if accessed_str else "")
        text += f". – {url_block}"
    else:
        # Сборник перед издательством
        if container:
            text += f" // {container}"

        areas: List[str] = []

        # Место: издательство, год
        pub_parts: List[str] = []
        if leg.get("publisher_place"):
            pub_parts.append(leg["publisher_place"])
        pub_tail = ", ".join(x for x in [leg.get("publisher"), leg.get("year")] if x)
        if pub_tail:
            pub_parts.append(pub_tail)
        if pub_parts:
            areas.append(" : ".join(pub_parts))

        if leg.get("volume"):
            areas.append(f"Т. {leg['volume']}" if not str(leg["volume"]).startswith("Т.") else str(leg["volume"]))

        if leg.get("page"):
            areas.append(f"С. {leg['page']}")
        elif leg.get("number_of_pages"):
            areas.append(f"{leg['number_of_pages']} с.")

        if leg.get("collection_title"):
            areas.append(f"({leg['collection_title']})")

        if url:
            accessed_str = _format_ru_date(leg.get("accessed_date"))
            url_block = f"URL: {url}" + (f" (дата обращения: {accessed_str})" if accessed_str else "")
            areas.append(url_block)

        if areas:
            text += ". – " + ". – ".join(areas)

    if leg.get("note"):
        text += f". – {leg['note']}"
    if leg.get("repealed"):
        text += ". – Утратил силу"

    return _cleanup_punctuation(_ensure_dot(text))


def render_single_citation(csl_item: Dict[str, Any], style_path: str = DEFAULT_CSL_PATH) -> str:
    """Рендерит одну библиографическую запись (CSL или спецформат для archive/legislation)"""
    item_type = csl_item.get("type")
    if item_type == "archive":
        return render_archive_citation(csl_item)
    if item_type == "legislation":
        return render_legislation_citation(csl_item)

    prepared = dict(csl_item)
    if not prepared.get("id"):
        prepared["id"] = "item_1"

    locale = _resolve_locale(prepared)
    style = _load_style(style_path, locale)

    bib_data = CiteProcJSON([prepared])
    bibliog = CitationStylesBibliography(style, bib_data, formatter.plain)
    bibliog.register(Citation([CitationItem(prepared["id"])]))

    rendered = [str(entry) for entry in bibliog.bibliography()]
    if not rendered:
        raise ValueError("Не удалось сгенерировать библиографическую ссылку.")

    body = _cleanup_punctuation(rendered[0])
    head = format_head_author(prepared.get("author"))
    if head:
        return f"{head} {body}"
    return body


def _sort_key(rendered_text: str) -> tuple:
    """Сначала кириллические потом зарубежные"""
    stripped = rendered_text.lstrip("«\"'([ ")
    is_foreign = 0 if (stripped and _CYRILLIC_RE.match(stripped[0])) else 1
    return (is_foreign, stripped.lower())


def generate_gost_bibliography_items(
    csl_items: List[Dict[str, Any]],
    style_path: str = DEFAULT_CSL_PATH,
    sort_russian_first: bool = True,
) -> List[Dict[str, Any]]:
    """Возвращает отсортированный список словарей {id, number, citation}"""
    if not csl_items:
        return []

    pairs = [
        (item.get("id") or f"item_{idx}", render_single_citation(item, style_path=style_path))
        for idx, item in enumerate(csl_items, start=1)
    ]

    if sort_russian_first:
        pairs.sort(key=lambda pair: _sort_key(pair[1]))

    return [
        {"id": item_id, "number": idx, "citation": text}
        for idx, (item_id, text) in enumerate(pairs, start=1)
    ]


def generate_gost_bibliography(
    csl_items: List[Dict[str, Any]],
    style_path: str = DEFAULT_CSL_PATH,
    sort_russian_first: bool = True,
    numbered: bool = False,
) -> List[str]:
    """Генерирует список библиографических записей"""
    items = generate_gost_bibliography_items(
        csl_items,
        style_path=style_path,
        sort_russian_first=sort_russian_first,
    )
    if numbered:
        return [f"{entry['number']}. {entry['citation']}" for entry in items]
    return [entry["citation"] for entry in items]


def generate_gost_citation(
    csl_json_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    style_path: str = DEFAULT_CSL_PATH,
) -> Union[str, List[str]]:
    """Обратно совместимая точка входа: dict -> str, list -> list[str]."""
    if isinstance(csl_json_data, dict):
        return render_single_citation(csl_json_data, style_path=style_path)
    if isinstance(csl_json_data, list):
        return generate_gost_bibliography(csl_json_data, style_path=style_path, sort_russian_first=False)
    raise ValueError("csl_json_data должен быть словарём (dict) или списком словарей (list).")