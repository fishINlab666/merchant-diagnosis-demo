"""Read bounded, source-faithful CSV and XLSX table previews."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

MAX_ROWS = 80
MAX_COLUMNS = 40


def clean_headers(values: list[Any]) -> list[str]:
    headers: list[str] = []
    seen: dict[str, int] = {}
    for index, value in enumerate(values[:MAX_COLUMNS]):
        base = str(value).strip() if value is not None and str(value).strip() else f'未命名列_{index + 1}'
        seen[base] = seen.get(base, 0) + 1
        headers.append(base if seen[base] == 1 else f'{base}__{seen[base]}')
    return headers


def clean_row(values: list[Any]) -> list[Any]:
    return [value for value in values[:MAX_COLUMNS]]


def read_csv_file(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    text = ''
    last_error: UnicodeDecodeError | None = None
    for encoding in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError as error:
            last_error = error
    if not text:
        raise ValueError(f'{path.name} 编码无法识别：{last_error}')
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(text.splitlines(), dialect))
    header_index = next((index for index, row in enumerate(rows) if any(str(cell).strip() for cell in row)), None)
    if header_index is None:
        raise ValueError(f'{path.name} 没有可读取的表头')
    headers = clean_headers(rows[header_index])
    data_rows = [clean_row(row) for row in rows[header_index + 1:] if any(str(cell).strip() for cell in row)][:MAX_ROWS]
    return [{'file_name': path.name, 'sheet_name': 'Sheet1', 'headers': headers, 'rows': data_rows}]


def read_xlsx_file(path: Path) -> list[dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    previews: list[dict[str, Any]] = []
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        header_index = next((index for index, row in enumerate(rows) if any(cell is not None and str(cell).strip() for cell in row)), None)
        if header_index is None:
            continue
        headers = clean_headers(list(rows[header_index]))
        data_rows = [clean_row(list(row)) for row in rows[header_index + 1:] if any(cell is not None and str(cell).strip() for cell in row)][:MAX_ROWS]
        previews.append({'file_name': path.name, 'sheet_name': sheet.title, 'headers': headers, 'rows': data_rows})
    workbook.close()
    if not previews:
        raise ValueError(f'{path.name} 没有可读取的工作表')
    return previews


def read_table_file(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f'输入文件不存在：{source}')
    suffix = source.suffix.lower()
    if suffix == '.csv':
        return read_csv_file(source)
    if suffix in ('.xlsx', '.xlsm'):
        return read_xlsx_file(source)
    raise ValueError(f'暂不支持 {suffix}，请提供 CSV 或 XLSX。')
