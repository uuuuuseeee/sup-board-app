"""
Utility functions and helpers for the application.
"""
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from markupsafe import Markup

# JST timezone (UTC+9)
JST = timezone(timedelta(hours=+9), "JST")
DATETIME_FMT = "%Y/%m/%d %H:%M"


def now_jst_str() -> str:
    """Get current time as JST-formatted string."""
    return datetime.now(JST).strftime(DATETIME_FMT)


def nl2br(s: Optional[str]) -> Markup | str:
    """Convert newlines to HTML <br> tags."""
    if s:
        return Markup(s.replace("\n", "<br>\n"))
    return ""


def natural_sort_key(text: Optional[str]) -> List[object]:
    """
    Natural sort key function (e.g., B2 < B10 handled correctly).
    Handles None and empty strings.
    """
    t = text or ""
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r"(\d+)", t)]


def to_int_or_none(value: Optional[str]) -> Optional[int]:
    """Convert string to int or None if conversion fails."""
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def get_selected_location(form) -> str:
    """
    Get location value from form (dropdown + other input field).
    """
    location_select = form.get("location_select")
    return form.get("location_other") if location_select == "その他" else (location_select or "")


def validated_order_param(order: Optional[str], default: str = "asc") -> str:
    """Validate order parameter, return default if invalid."""
    return order if order in {"asc", "desc"} else default


def validated_sort_by_param(sort_by: Optional[str], default: str = "id") -> str:
    """Validate sort_by parameter. Currently supports: id / name."""
    return sort_by if sort_by in {"id", "name"} else default
