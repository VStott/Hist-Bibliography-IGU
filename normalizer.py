import re
from typing import Any, Dict, List, Optional

LANG_MAP = {
    "ru": "ru", "ru-ru": "ru", "rus": "ru", "russian": "ru", "русский": "ru",
    "en": "en", "en-us": "en", "en-gb": "en", "eng": "en", "english": "en", "английский": "en",
    "fr": "fr", "fr-fr": "fr", "fra": "fr", "french": "fr", "francais": "fr", "français": "fr", "французский": "fr",
    "de": "de", "de-de": "de", "ger": "de", "deu": "de", "german": "de", "deutsch": "de", "немецкий": "de",
}

_ISO_DATE_RE = re.compile(r"^\s*(\d{4})[-./,\s]+(\d{1,2})(?:[-./,\s]+(\d{1,2}))?\s*$")
_DMY_DATE_RE = re.compile(r"^\s*(\d{1,2})[-./](\d{1,2})[-./](\d{4})\s*$")
_MY_DATE_RE = re.compile(r"^\s*(\d{1,2})[-./](\d{4})\s*$")
_YEAR_ONLY_RE = re.compile(r"^\s*(\d{4})\s*$")


def safe_str(val: Any) -> Optional[str]:
    """Превращает в непустую строку"""
    if val is None:
        return None
    text = str(val).strip()
    return text if text else None


def normalize_initials(given: str) -> str:
    """Инициалы с сохранением - между двойными именами"""
    text = given.strip()
    text = re.sub(r"\.(?=[^\s\-\.,;])", ". ", text)
    return re.sub(r"\s+", " ", text)


def clean_persons(persons_input: Any) -> List[Dict[str, str]]:
    """Универсальная очистка и парсинг списка людей (принимает list или str)."""
    cleaned: List[Dict[str, str]] = []
    if not persons_input:
        return cleaned

    if isinstance(persons_input, str):
        raw_list = [p.strip() for p in persons_input.split(",") if p.strip()]
        for item in raw_list:
            parts = item.split()
            if parts:
                family = parts[0]
                given = normalize_initials(" ".join(parts[1:])) if len(parts) > 1 else ""
                cleaned.append({"family": family, "given": given})
        return cleaned

    if isinstance(persons_input, list):
        for person in persons_input:
            if isinstance(person, dict):
                family = str(person.get("family", "")).strip()
                given = normalize_initials(str(person.get("given", "")))
                literal = str(person.get("literal", "")).strip()
                if literal:
                    cleaned.append({"literal": literal})
                elif family or given:
                    cleaned.append({"family": family, "given": given})
            elif isinstance(person, str) and person.strip():
                cleaned.extend(clean_persons(person))
    return cleaned


def clean_contributors(val: Any) -> List[Dict[str, str]]:
    """Коллективный и/или безличный автор"""
    if not val:
        return []
    if isinstance(val, str):
        items = [s.strip() for s in val.split(";") if s.strip()]
        return [{"literal": item} for item in items]
    if isinstance(val, list):
        result: List[Dict[str, str]] = []
        for item in val:
            if isinstance(item, str) and item.strip():
                result.append({"literal": item.strip()})
            elif isinstance(item, dict):
                if item.get("literal"):
                    result.append({"literal": str(item["literal"]).strip()})
                elif item.get("family") or item.get("given"):
                    result.append({
                        "family": str(item.get("family", "")).strip(),
                        "given": normalize_initials(str(item.get("given", ""))),
                    })
        return result
    return []


def _validate_date_parts(parts: List[int]) -> Optional[Dict[str, List[List[int]]]]:
    """Корректность дат"""
    if not parts:
        return None
    year = parts[0]
    if not (1 <= year <= 9999):
        return None
    if len(parts) >= 2 and not (1 <= parts[1] <= 12):
        return None
    if len(parts) >= 3 and not (1 <= parts[2] <= 31):
        return None
    return {"date-parts": [parts[:3]]}


def parse_date(date_input: Any) -> Optional[Dict[str, List[List[int]]]]:
    """Парсит даты в строгий CSL-JSON формат {"date-parts": [[YYYY, MM, DD]]}."""
    if not date_input:
        return None

    if isinstance(date_input, dict) and "date-parts" in date_input:
        raw_parts = date_input["date-parts"]
        if isinstance(raw_parts, list) and raw_parts and isinstance(raw_parts[0], list):
            return parse_date(raw_parts[0])
        return None

    if isinstance(date_input, int):
        return _validate_date_parts([date_input])

    if isinstance(date_input, (list, tuple)):
        nums: List[int] = []
        for item in date_input:
            try:
                nums.append(int(item))
            except (ValueError, TypeError):
                continue
        if not nums:
            return None
        if len(nums) == 3 and nums[0] <= 31 and nums[2] >= 1000:
            nums = [nums[2], nums[1], nums[0]]
        elif len(nums) == 2 and nums[0] <= 12 and nums[1] >= 1000:
            nums = [nums[1], nums[0]]
        return _validate_date_parts(nums)

    if isinstance(date_input, str):
        text = date_input.strip()
        if not text:
            return None

        m = _ISO_DATE_RE.match(text)
        if m:
            parts = [int(m.group(1)), int(m.group(2))]
            if m.group(3):
                parts.append(int(m.group(3)))
            return _validate_date_parts(parts)

        m = _DMY_DATE_RE.match(text)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return _validate_date_parts([year, month, day])

        m = _MY_DATE_RE.match(text)
        if m:
            month, year = int(m.group(1)), int(m.group(2))
            return _validate_date_parts([year, month])

        m = _YEAR_ONLY_RE.match(text)
        if m:
            return _validate_date_parts([int(m.group(1))])

        year_match = re.search(r"\b(\d{4})\b", text)
        if year_match:
            return _validate_date_parts([int(year_match.group(1))])

    return None


parse_issued_date = parse_date


def normalize_page_range(page: Optional[str]) -> Optional[str]:
    """По требованиям диапозон страниц всегда т.н. короткое тире"""
    if not page:
        return None
    return re.sub(r"(\d)\s*[-‑–—]\s*(\d)", r"\1–\2", page.strip())


def normalize_language(raw_lang: Any) -> str:
    """Нормализует код языка в один из 'ru', 'en', 'fr', 'de'"""
    if not raw_lang:
        return "ru"
    key = str(raw_lang).lower().strip()
    return LANG_MAP.get(key, "ru")


def _parse_archive_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "archive_name": safe_str(data.get("archive_name") or data.get("title")) or "",
        "archive_abbr": safe_str(data.get("archive_abbr")),
        "fond": safe_str(data.get("archive_fond") or data.get("fond")),
        "opis": safe_str(data.get("archive_opis") or data.get("opis")),
        "sub_unit": safe_str(data.get("archive_sub_unit") or data.get("sub_unit")),
        "delo_type": safe_str(data.get("archive_delo_type") or data.get("delo_type")) or "Д.",
        "delo": safe_str(data.get("archive_delo") or data.get("delo")),
        "list_num": normalize_page_range(
            safe_str(data.get("archive_list") or data.get("list_num") or data.get("page"))
        ),
        "doc_title": safe_str(data.get("archive_doc_title") or data.get("note")),
    }


def _parse_normative_acts(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": safe_str(data.get("title")) or "",
        "law_type": safe_str(data.get("law_type")),
        "law_number": safe_str(data.get("law_number")),
        "adoption_info": safe_str(data.get("adoption_info")),
        "container_title": safe_str(data.get("container_title")),
        "publisher_place": safe_str(data.get("publisher_place")),
        "publisher": safe_str(data.get("publisher")),
        "year": safe_str(data.get("year")),
        "volume": safe_str(data.get("volume")),
        "page": normalize_page_range(safe_str(data.get("page"))),
        "number_of_pages": safe_str(data.get("number_of_pages")),
        "collection_title": safe_str(data.get("collection_title")),
        "url": safe_str(data.get("url") or data.get("URL")),
        "accessed_date": parse_date(data.get("accessed_date") or data.get("accessed")),
        "repealed": bool(data.get("repealed", False)),
        "note": safe_str(data.get("note") or data.get("extra")),
    }


def parser(data: Dict[str, Any]) -> Dict[str, Any]:
    """Преобразует входной словарь API в валидный объект CSL-JSON (или спец-структуру для archive/legislation)."""
    if not isinstance(data, dict):
        raise ValueError("Ожидается JSON-объект (dict) с данными источника.")

    item_type = safe_str(data.get("type")) or "book"
    clean_lang = normalize_language(data.get("language", "ru"))

    csl_item: Dict[str, Any] = {
        "id": safe_str(data.get("id")) or "item_1",
        "type": item_type,
        "title": safe_str(data.get("title")) or "",
        "language": clean_lang,
    }

    if item_type == "archive":
        csl_item["archive_data"] = _parse_archive_fields(data)
        return csl_item

    if item_type == "legislation":
        csl_item["legislation_data"] = _parse_normative_acts(data)
        return csl_item

    # 1) Авторы и прочие
    roles_map = {
        "author": data.get("authors") or data.get("author"),
        "container-author": data.get("container_authors") or data.get("container-author"),
        "editor": data.get("editors") or data.get("editor"),
        "translator": data.get("translators") or data.get("translator"),
        "collection-editor": (
            data.get("preface_authors")
            or data.get("collection_editors")
            or data.get("collection-editor")
        ),
    }

    for csl_key, raw_val in roles_map.items():
        parsed_people = clean_persons(raw_val)
        if parsed_people:
            csl_item[csl_key] = parsed_people

    contributors = clean_contributors(data.get("contributors") or data.get("contributor"))
    if contributors:
        csl_item["contributor"] = contributors

    # 2) Текстовые поля
    fields = {
        "container-title": data.get("container_title") or data.get("container-title"),
        "collection-title": data.get("collection_title") or data.get("collection-title"),
        "edition": data.get("edition"),
        "event-title": data.get("event_title") or data.get("event-title"),
        "publisher-place": data.get("publisher_place") or data.get("publisher-place"),
        "publisher": data.get("publisher"),
        "original-publisher": (
            data.get("translation_language")
            or data.get("original_publisher")
            or data.get("original-publisher")
        ),
        "medium": data.get("site_type") or data.get("medium"),
        "number-of-volumes": data.get("number_of_volumes") or data.get("number-of-volumes"),
        "volume": data.get("volume"),
        "issue": data.get("issue"),
        "number-of-pages": data.get("number_of_pages") or data.get("number-of-pages"),
        "ISBN": data.get("isbn") or data.get("ISBN"),
        "DOI": data.get("doi") or data.get("DOI"),
        "URL": data.get("url") or data.get("URL"),
        "note": data.get("note") or data.get("extra"),
    }

    for csl_key, raw_val in fields.items():
        val = safe_str(raw_val)
        if val:
            csl_item[csl_key] = val

    page = normalize_page_range(safe_str(data.get("page")))
    if page:
        csl_item["page"] = page

    # 3) Даты
    issued = parse_date(data.get("issued") or data.get("year"))
    if issued:
        csl_item["issued"] = issued

    accessed = parse_date(data.get("accessed_date") or data.get("accessed"))
    if accessed:
        csl_item["accessed"] = accessed

    return csl_item