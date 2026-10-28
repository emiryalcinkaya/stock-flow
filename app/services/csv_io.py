"""CSV helpers that work with Excel in English, Turkish and German locales.

Excel in Turkish/German uses ";" as the separator and "," as the decimal mark,
so exports can use either separator and imports detect it automatically.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional, Sequence

from fastapi.responses import Response


def csv_response(filename: str, header: Sequence[str], rows: Iterable[Sequence], delimiter: str = ",") -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])

    # The BOM makes Excel open the file as UTF-8 (needed for ç, ğ, ü, ß, ...).
    content = "﻿" + buffer.getvalue()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def format_number(value, decimal_comma: bool) -> str:
    if value is None:
        return ""
    text = format(Decimal(value).normalize(), "f")
    return text.replace(".", ",") if decimal_comma else text


def read_rows(text: str) -> List[dict]:
    """Parse CSV text into dicts keyed by lower-case header names."""
    text = text.lstrip("﻿")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []

    header = [cell.strip().lower() for cell in rows[0]]
    return [
        {header[i]: (row[i].strip() if i < len(row) else "") for i in range(len(header))}
        for row in rows[1:]
    ]


def parse_decimal(value: str) -> Optional[Decimal]:
    """Accepts 1234.5, 1234,5, 1.234,5 and 1,234.5. Empty means None."""
    value = (value or "").strip().replace(" ", "").replace(" ", "")
    if not value:
        return None

    if "," in value and "." in value:
        # The separator that appears last is the decimal mark.
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")

    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"'{value}' is not a number") from None
