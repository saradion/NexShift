import datetime as dt
import re

import jdatetime

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")


def to_jalali_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        value = value.date()
    j = jdatetime.date.fromgregorian(date=value)
    return f"{j.year:04d}-{j.month:02d}-{j.day:02d}"


def parse_date_string(text) -> dt.date:
    cleaned = str(text).strip().translate(_DIGITS)
    match = _DATE_RE.match(cleaned)
    if not match:
        raise ValueError("Unrecognised date format")
    year, month, day = (int(x) for x in match.groups())
    if year >= 1700:
        return dt.date(year, month, day)
    return jdatetime.date(year, month, day).togregorian()