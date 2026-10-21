"""Exports opened in Excel/Sheets: text that starts like a formula is neutralised (CSV/formula injection).
Customer names and notes come from the public menu, so a name such as =HYPERLINK(...) must stay plain text."""
import csv

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


class SafeCsvWriter:
    def __init__(self, buffer, **kwargs):
        self._writer = csv.writer(buffer, **kwargs)

    def writerow(self, row) -> None:
        self._writer.writerow([safe_cell(value) for value in row])


def neutralise_formulas(sheet) -> None:
    """openpyxl turns any string starting with '=' into a formula; keep them as literal text instead."""
    for row in sheet.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                cell.data_type = "s"
