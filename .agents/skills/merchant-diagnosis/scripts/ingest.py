"""Read local material into evidence fragments, without interpreting business fields.

Limits fail the whole read rather than silently dropping rows, cells or pages.
Dependencies for XLSX/PDF are optional; image OCR is explicitly unsupported.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, time
import hashlib
from html.parser import HTMLParser
from io import BytesIO, StringIO
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARACTERS = 2_000_000
MAX_FRAGMENTS = 50_000
MAX_XLSX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_XLSX_CELLS = 200_000
MAX_PDF_PAGES = 200


class MaterialError(ValueError):
    """The material could not be read completely within the supported scope."""


class _Fragments:
    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []
        self.characters = 0

    def add(self, locator: str, text: str) -> None:
        self.characters += len(text)
        if self.characters > MAX_TEXT_CHARACTERS:
            raise MaterialError(f"提取文字超限（{MAX_TEXT_CHARACTERS} 字符）；请按期间或门店拆分材料。")
        if len(self.items) >= MAX_FRAGMENTS:
            raise MaterialError(f"材料片段超限（{MAX_FRAGMENTS} 条）；请拆分材料。")
        self.items.append({"locator": locator, "text": text})


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=lambda item: item.isoformat() if isinstance(item, (date, datetime, time)) else str(item))


def _utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise MaterialError("文本不是 UTF-8 编码；请另存为 UTF-8 CSV／TSV／文本后重试。") from None


def _read_delimited(data: bytes, delimiter: str, fragments: _Fragments) -> None:
    has_content = False
    # The standard csv limit is lower than our explicit document limit.
    old_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_TEXT_CHARACTERS)
    try:
        for number, row in enumerate(csv.reader(StringIO(_utf8(data), newline=""), delimiter=delimiter, strict=True), 1):
            has_content = has_content or any(value.strip() for value in row)
            fragments.add(f"row:{number}", _json(row))
    except csv.Error:
        raise MaterialError("CSV／TSV 格式损坏或单字段超限；请检查引号、分隔符并拆分过长字段。") from None
    finally:
        csv.field_size_limit(old_limit)
    if not has_content:
        raise MaterialError("表格没有可读取内容；请提供含表头、记录或备注的文件。")


class _VisibleHTML(HTMLParser):
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    _NON_VISIBLE = {"head", "script", "style", "template", "noscript"}

    def __init__(self, fragments: _Fragments) -> None:
        super().__init__(convert_charrefs=True)
        self.fragments = fragments
        self.stack: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        style = (attributes.get("style") or "").replace(" ", "").lower()
        hidden = any(item[1] for item in self.stack) or tag in self._NON_VISIBLE or "hidden" in attributes or attributes.get("aria-hidden", "").lower() == "true" or "display:none" in style or "visibility:hidden" in style
        if tag not in self._VOID:
            self.stack.append((tag, hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if data.strip() and not any(item[1] for item in self.stack):
            self.fragments.add(f"html:{len(self.fragments.items) + 1}(line:{self.getpos()[0]})", data)


def _read_xlsx(data: bytes, fragments: _Fragments, warnings: list[str]) -> None:
    try:
        import openpyxl
    except ImportError:
        raise MaterialError("读取 XLSX 需要 openpyxl；请使用含该依赖的 Python，或另存 UTF-8 CSV。") from None
    with ZipFile(BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_XLSX_EXPANDED_BYTES:
            raise MaterialError(f"XLSX 解压内容超限（{MAX_XLSX_EXPANDED_BYTES} 字节）；请拆分工作簿。")
    workbook = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=False)
    cached = None
    try:
        cached = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
        scanned_cells = 0
        formula_seen = False
        for sheet in workbook.worksheets:
            # Exporters sometimes omit or understate worksheet dimensions.
            # Read the actual XML rows, then enforce limits on traversed cells.
            sheet.reset_dimensions()
            cached[sheet.title].reset_dimensions()
            if sheet.sheet_state != "visible":
                warnings.append(f"sheet:{sheet.title} 为隐藏工作表，内容仍已读取。")
            before = len(fragments.items)
            for row, cache_row in zip(sheet.iter_rows(), cached[sheet.title].iter_rows(), strict=True):
                scanned_cells += max(len(row), 1)
                if scanned_cells > MAX_XLSX_CELLS:
                    raise MaterialError(f"XLSX 工作表范围超限（{MAX_XLSX_CELLS} 单元格）；请拆分或移除多余空白格式。")
                for cell, cache_cell in zip(row, cache_row, strict=True):
                    if cell.value is None:
                        continue
                    locator = f"sheet:{sheet.title}!{cell.coordinate}"
                    if cell.data_type == "f":
                        formula_seen = True
                        value = {"formula": cell.value, "cached_value": cache_cell.value}
                        if cache_cell.value is None:
                            warnings.append(f"{locator} 公式无缓存值；未计算或补造结果，请在表格软件重算后另存。")
                    else:
                        value = {"value": cell.value}
                    if cell.number_format != "General":
                        value["number_format"] = cell.number_format
                    fragments.add(locator, _json(value))
            if len(fragments.items) == before:
                warnings.append(f"sheet:{sheet.title} 没有可读取单元格内容。")
        if formula_seen:
            warnings.append("公式与文件中的缓存值已保留；缓存可能过期，本读取器不执行公式，也不把缓存当作重算结果。")
        warnings.append("XLSX 读取所有工作表的单元格值、公式和数字格式；图表、图片、批注及版式不作为已读取证据。")
    finally:
        workbook.close()
        if cached is not None:
            cached.close()


def _read_pdf(data: bytes, fragments: _Fragments, warnings: list[str]) -> None:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise MaterialError("读取 PDF 需要 pypdf；请使用含该依赖的 Python，或提供文字／CSV 材料。") from None
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise MaterialError("PDF 已加密；请提供可读取的副本或文字材料。")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise MaterialError(f"PDF 页数超限（{MAX_PDF_PAGES} 页）；请按相关章节拆分。")
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if text.strip():
            fragments.add(f"page:{number}", text)
        else:
            warnings.append(f"page:{number} 未提取到文字，可能为空白或扫描页；如有内容请补文字或 OCR 结果。")
    if not fragments.items:
        raise MaterialError("PDF 没有可提取文字；扫描件请先 OCR，或提供原表／文字材料。")
    warnings.append("PDF 按页提取文字，未还原表格版式；跨列顺序及图片中的内容需对照原件核对。")


def read_material(path: str | Path) -> dict[str, Any]:
    """Read a supported local file without transmitting it or executing its content."""
    path = Path(path)
    name = path.name
    try:
        if not path.is_file():
            raise MaterialError(f"材料 {name} 不存在或不是普通文件。")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise MaterialError(f"材料 {name} 文件大小超限（{MAX_FILE_BYTES} 字节）；请拆分后读取。")
        data = path.read_bytes()
    except OSError:
        raise MaterialError(f"无法读取材料 {name}；请检查文件是否存在及读取权限。") from None
    if len(data) > MAX_FILE_BYTES:
        raise MaterialError(f"材料 {name} 文件大小超限（{MAX_FILE_BYTES} 字节）。")
    if not data:
        raise MaterialError(f"材料 {name} 为空文件。")
    suffix = path.suffix.lower()
    fragments = _Fragments()
    warnings: list[str] = []
    try:
        if suffix in {".csv", ".tsv"}:
            _read_delimited(data, "\t" if suffix == ".tsv" else ",", fragments)
        elif suffix in {".txt", ".md", ".markdown"}:
            for number, line in enumerate(_utf8(data).splitlines(), 1):
                if line.strip():
                    fragments.add(f"line:{number}", line)
        elif suffix in {".html", ".htm"}:
            parser = _VisibleHTML(fragments)
            parser.feed(_utf8(data))
            parser.close()
            warnings.append("HTML 仅读取本地可见文本，不执行脚本、不访问链接；外部 CSS、动态内容、图片及版式未读取。")
        elif suffix == ".xlsx":
            _read_xlsx(data, fragments, warnings)
        elif suffix == ".pdf":
            _read_pdf(data, fragments, warnings)
        elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".heic"}:
            raise MaterialError("图片 OCR 在当前版本未启用；请提供原始 XLSX、CSV 或人工核对后的文字，图片未被当作已读取材料。")
        else:
            raise MaterialError(f"不支持 {suffix or '无扩展名'} 格式；请转换为 xlsx、UTF-8 CSV／TSV／文本或文本 PDF。")
    except MaterialError:
        raise
    except Exception as error:
        raise MaterialError(f"材料 {name} 解析失败（{type(error).__name__}）；请检查格式或重新导出。") from None
    if not fragments.items:
        raise MaterialError(f"材料 {name} 没有可读取文字或单元格；请提供原表／文字。")
    return {"name": name, "sha256": hashlib.sha256(data).hexdigest(), "fragments": fragments.items, "warnings": warnings}
