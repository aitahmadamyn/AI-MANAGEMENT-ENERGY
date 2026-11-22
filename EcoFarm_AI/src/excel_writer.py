"""
EcoFarm Circular — Pure-Stdlib Typed Excel (.xlsx) & Windows-Safe ZIP Writer
============================================================================

Generates genuine OpenXML `.xlsx` workbooks with explicit Excel numeric cell
types (`t="n"`) for integers/floats and `t="inlineStr"` for text, ensuring
French/international Windows Excel & WPS Spreadsheets never collapse comma CSVs
into single text columns or misparse decimal dots.

Also provides a Windows Explorer / macOS / Linux / Google Colab compatible ZIP
writer normalizing archive paths and permissions (`create_system=0`, `0o644`).
"""

from __future__ import annotations

import csv
import datetime as dt
import math
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

_INT_RE = re.compile(r"^-?(?:0|[1-9]\d*)$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize_xml_text(text: str) -> str:
    return escape(_CTRL_CHARS_RE.sub("", text))


def _col_letter(col_idx_1based: int) -> str:
    letters: List[str] = []
    n = col_idx_1based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def parse_typed_cell(raw: Any) -> Tuple[str, Any]:
    """
    Classify any CSV/dict cell value cleanly into ('n', number_str) vs ('s', text).
    Prevents scientific-notation strings with trailing whitespace or leading-zero
    numeric IDs from losing formatting while guaranteeing every real int/float is numeric.
    """
    if raw is None:
        return "empty", ""
    if isinstance(raw, bool):
        return "n", "1" if raw else "0"
    if isinstance(raw, int):
        return "n", str(raw)
    if isinstance(raw, float):
        if not math.isfinite(raw):
            return "s", str(raw)
        return "n", repr(raw)

    s = str(raw).strip()
    if s == "":
        return "empty", ""
    if _INT_RE.match(s):
        return "n", s
    if _FLOAT_RE.match(s):
        try:
            f = float(s)
            if math.isfinite(f):
                # Preserve exact clean decimal string for non-scientific numbers when valid
                if "e" not in s.lower() and not s.startswith(".") and not s.endswith("."):
                    return "n", s.lstrip("+")
                return "n", repr(f)
        except ValueError:
            pass
    return "s", s


def _build_worksheet_xml(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    max_col = max(1, len(headers))
    col_widths = [max(10, min(42, len(str(h)) + 4)) for h in headers]

    row_xml_parts: List[str] = []
    # Header row (row 1, style 1 = bold slate fill)
    hdr_cells = []
    for c_idx, h in enumerate(headers, start=1):
        ref = f"{_col_letter(c_idx)}1"
        hdr_cells.append(f'<c r="{ref}" s="1" t="inlineStr"><is><t>{_sanitize_xml_text(str(h))}</t></is></c>')
    row_xml_parts.append(f'<row r="1" ht="20" customHeight="1">{"".join(hdr_cells)}</row>')

    row_count = 1
    for r_idx, row in enumerate(rows, start=2):
        row_count = r_idx
        cells_xml: List[str] = []
        for c_idx, val in enumerate(row, start=1):
            kind, parsed = parse_typed_cell(val)
            if kind == "empty":
                continue
            ref = f"{_col_letter(c_idx)}{r_idx}"
            if r_idx <= 200:
                col_widths[c_idx - 1] = max(col_widths[c_idx - 1], min(44, len(parsed) + 3))
            if kind == "n":
                cells_xml.append(f'<c r="{ref}" t="n"><v>{parsed}</v></c>')
            else:
                cells_xml.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{_sanitize_xml_text(parsed)}</t></is></c>'
                )
        row_xml_parts.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

    cols_xml = "".join(
        f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
        for i, w in enumerate(col_widths, start=1)
    )
    dim_ref = f"A1:{_col_letter(max_col)}{row_count}"

    xml_str = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dim_ref}"/>'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<cols>{cols_xml}</cols>'
        f'<sheetData>{"".join(row_xml_parts)}</sheetData>'
        f'<autoFilter ref="{dim_ref}"/>'
        '</worksheet>'
    )
    return xml_str.encode("utf-8")


_STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="2">'
    '<font><sz val="10"/><name val="Calibri"/><color rgb="FF0F172A"/></font>'
    '<font><b/><sz val="10"/><name val="Calibri"/><color rgb="FF0F172A"/></font>'
    '</fonts>'
    '<fills count="3">'
    '<fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFF1F5F9"/></patternFill></fill>'
    '</fills>'
    '<borders count="2">'
    '<border><left/><right/><top/><bottom/><diagonal/></border>'
    '<border><left/><right/><top/><bottom style="thin"><color rgb="FFCBD5E1"/></bottom><diagonal/></border>'
    '</borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="2">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>'
    '</cellXfs>'
    '</styleSheet>'
).encode("utf-8")

_RELS_ROOT_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    '</Relationships>'
).encode("utf-8")


def write_xlsx_sheets(
    xlsx_path: Path,
    sheets: Sequence[Tuple[str, Sequence[str], Iterable[Sequence[Any]]]],
) -> None:
    """Write a native OpenXML `.xlsx` workbook with 1+ sheets and genuine `t="n"` numeric typing."""
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    fixed_dt = (2026, 11, 21, 12, 0, 0)

    def _put(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
        zi = zipfile.ZipInfo(name, date_time=fixed_dt)
        zi.create_system = 0
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        zf.writestr(zi, data)

    sheet_entries: List[Tuple[str, bytes]] = []
    used_names: set[str] = set()
    for idx, (raw_name, headers, rows) in enumerate(sheets, start=1):
        clean_name = re.sub(r"[\\/*?:\[\]]", "_", raw_name)[:31] or f"Sheet{idx}"
        while clean_name in used_names:
            clean_name = f"{clean_name[:28]}_{idx}"
        used_names.add(clean_name)
        sheet_entries.append((clean_name, _build_worksheet_xml(headers, rows)))

    content_types_overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    workbook_sheets = []
    wb_rels = [
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    ]
    for idx, (sname, _) in enumerate(sheet_entries, start=1):
        content_types_overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        workbook_sheets.append(f'<sheet name="{_sanitize_xml_text(sname)}" sheetId="{idx}" r:id="rId{idx}"/>')
        wb_rels.append(
            f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'{"".join(content_types_overrides)}'
        '</Types>'
    ).encode("utf-8")

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(workbook_sheets)}</sheets>'
        '</workbook>'
    ).encode("utf-8")

    wb_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(wb_rels)}'
        '</Relationships>'
    ).encode("utf-8")

    with zipfile.ZipFile(xlsx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _put(zf, "[Content_Types].xml", content_types_xml)
        _put(zf, "_rels/.rels", _RELS_ROOT_XML)
        _put(zf, "xl/workbook.xml", workbook_xml)
        _put(zf, "xl/_rels/workbook.xml.rels", wb_rels_xml)
        _put(zf, "xl/styles.xml", _STYLES_XML)
        for idx, (_, sheet_xml) in enumerate(sheet_entries, start=1):
            _put(zf, f"xl/worksheets/sheet{idx}.xml", sheet_xml)


def csv_to_typed_xlsx(csv_path: Path, xlsx_path: Path, sheet_name: Optional[str] = None) -> int:
    """Convert any UTF-8 CSV into a strictly typed OpenXML `.xlsx` workbook."""
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        rows = list(reader)
    title = sheet_name or csv_path.stem[:31]
    write_xlsx_sheets(xlsx_path, [(title, headers, rows)])
    return len(rows)


def create_windows_compatible_zip(
    zip_path: Path,
    entries: Sequence[Tuple[Path, str]],
) -> int:
    """
    Package files into a CRC-verified ZIP archive with FAT/Windows-safe metadata
    (`create_system=0`, standard `0o644` permissions so read-only `0o444` raw CSVs
    never block extraction on Windows Explorer or Google Drive).
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    added = 0
    seen_arcs: set[str] = set()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp, raw_arc in sorted(entries, key=lambda x: x[1]):
            arc = raw_arc.replace("\\", "/")
            if not fp.is_file() or "__pycache__" in fp.parts or arc in seen_arcs:
                continue
            seen_arcs.add(arc)
            mtime = dt.datetime.fromtimestamp(fp.stat().st_mtime)
            zdt = (
                max(1980, mtime.year),
                mtime.month,
                mtime.day,
                mtime.hour,
                mtime.minute,
                mtime.second,
            )
            zi = zipfile.ZipInfo(arc, date_time=zdt)
            zi.create_system = 0
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, fp.read_bytes())
            added += 1

    with zipfile.ZipFile(zip_path, "r") as zchk:
        bad = zchk.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC verification failed on {zip_path.name} member {bad}")
    return added
