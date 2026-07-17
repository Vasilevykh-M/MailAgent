"""Normalize version-specific PaddleOCR results into the stable public contract."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.schemas.documents import DocumentElement, DocumentPage, DocumentParseResponse
from app.schemas.ocr import OcrLine, OcrPage, OcrResponse
from app.services.file_processor import ProcessedFile


def _primitive(value: Any) -> Any:
    """Convert Paddle/NumPy values to JSON-compatible Python values."""

    if hasattr(value, "tolist"):
        return _primitive(value.tolist())
    if isinstance(value, Mapping):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_primitive(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _result_mapping(result: Any) -> dict[str, Any]:
    """Read PaddleX's public ``.json['res']`` output without exposing it."""

    candidate: Any = result
    if not isinstance(candidate, Mapping):
        json_value = getattr(candidate, "json", None)
        if callable(json_value):
            json_value = json_value()
        if json_value is not None:
            candidate = json_value
        elif hasattr(candidate, "to_dict"):
            candidate = candidate.to_dict()
    if isinstance(candidate, str):
        candidate = json.loads(candidate)
    if not isinstance(candidate, Mapping):
        raise ValueError("PaddleOCR returned an unsupported result object")
    candidate = _primitive(candidate)
    content = candidate.get("res", candidate)
    if not isinstance(content, Mapping):
        raise ValueError("PaddleOCR result does not contain a mapping")
    return dict(content)


def _polygon(value: Any) -> list[list[int | float]] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    polygon: list[list[int | float]] = []
    for point in value:
        if isinstance(point, Sequence) and not isinstance(point, (str, bytes)) and len(point) >= 2:
            x, y = point[0], point[1]
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                polygon.append([x, y])
    return polygon or None


def normalize_ocr(
    results: list[Any],
    document: ProcessedFile,
    *,
    request_id: str,
    model: str,
    language: str,
    return_boxes: bool,
    return_confidence: bool,
    processing_time_ms: int,
) -> OcrResponse:
    pages: list[OcrPage] = []
    for fallback_index, result in enumerate(results):
        data = _result_mapping(result)
        page_index = int(data.get("page_index") if data.get("page_index") is not None else fallback_index)
        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])
        polygons = data.get("rec_polys", data.get("dt_polys", []))
        lines = [
            OcrLine(
                text=str(text),
                confidence=float(scores[index]) if return_confidence and index < len(scores) else None,
                polygon=_polygon(polygons[index]) if return_boxes and index < len(polygons) else None,
            )
            for index, text in enumerate(texts)
        ]
        width, height = _page_dimensions(data, document, page_index, fallback_index)
        pages.append(
            OcrPage(
                page_index=page_index,
                width=width,
                height=height,
                text="\n".join(line.text for line in lines),
                lines=lines,
            )
        )
    # A valid image/PDF is always one or more pages. This fallback protects the
    # public schema if a pipeline returns no prediction for a blank page.
    if not pages:
        for index, (width, height) in enumerate(document.dimensions):
            pages.append(OcrPage(page_index=index, width=width, height=height, text="", lines=[]))
    pages.sort(key=lambda page: page.page_index)
    return OcrResponse(
        request_id=request_id,
        model=model,
        language=language,
        page_count=len(pages),
        text="\n".join(page.text for page in pages if page.text),
        pages=pages,
        processing_time_ms=processing_time_ms,
    )


def normalize_document(
    results: list[Any],
    document: ProcessedFile,
    *,
    request_id: str,
    model: str,
    language: str,
    output_format: str,
    processing_time_ms: int,
) -> DocumentParseResponse:
    pages: list[DocumentPage] = []
    markdown_parts: list[str] = []
    for fallback_index, result in enumerate(results):
        data = _result_mapping(result)
        page_index = int(data.get("page_index") if data.get("page_index") is not None else fallback_index)
        width, height = _page_dimensions(data, document, page_index, fallback_index)
        tables = _table_lookup(data.get("table_res_list", []))
        formulas = _formula_lookup(data.get("formula_res_list", []))
        elements = [
            _document_element(item, page_index, order, tables, formulas)
            for order, item in enumerate(data.get("parsing_res_list", []))
            if isinstance(item, Mapping)
        ]
        pages.append(DocumentPage(page_index=page_index, width=width, height=height, elements=elements))
        if output_format in {"markdown", "both"}:
            markdown = _markdown(result, data)
            if markdown:
                markdown_parts.append(markdown)
    if not pages:
        for index, (width, height) in enumerate(document.dimensions):
            pages.append(DocumentPage(page_index=index, width=width, height=height, elements=[]))
    pages.sort(key=lambda page: page.page_index)
    return DocumentParseResponse(
        request_id=request_id,
        model=model,
        language=language,
        page_count=len(pages),
        pages=pages,
        markdown="\n\n".join(markdown_parts) if output_format in {"markdown", "both"} else None,
        processing_time_ms=processing_time_ms,
    )


def _page_dimensions(
    data: Mapping[str, Any], document: ProcessedFile, page_index: int, fallback_index: int
) -> tuple[int | None, int | None]:
    if isinstance(data.get("width"), (int, float)) and isinstance(data.get("height"), (int, float)):
        return int(data["width"]), int(data["height"])
    index = page_index if 0 <= page_index < len(document.dimensions) else fallback_index
    return document.dimensions[index] if 0 <= index < len(document.dimensions) else (None, None)


def _table_lookup(raw_tables: Any) -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_tables, Sequence) or isinstance(raw_tables, (str, bytes)):
        return tables
    for table in raw_tables:
        if isinstance(table, Mapping):
            key = table.get("table_region_id", table.get("region_id"))
            if key is not None:
                tables[str(key)] = _primitive(table)
    return tables


def _formula_lookup(raw_formulas: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_formulas, Sequence) or isinstance(raw_formulas, (str, bytes)):
        return []
    return [_primitive(item) for item in raw_formulas if isinstance(item, Mapping)]


def _document_element(
    raw: Mapping[str, Any],
    page_index: int,
    fallback_order: int,
    tables: dict[str, dict[str, Any]],
    formulas: list[dict[str, Any]],
) -> DocumentElement:
    block_id = raw.get("block_id", fallback_order)
    block_type = str(raw.get("block_label", raw.get("label", "unknown")))
    content = raw.get("block_content", raw.get("content"))
    bbox = raw.get("block_bbox", raw.get("bbox"))
    table = tables.get(str(block_id)) if block_type in {"table", "chart"} else None
    formula = None
    if block_type in {"formula", "equation"}:
        formula_data = formulas[fallback_order] if fallback_order < len(formulas) else {}
        formula = str(formula_data.get("rec_formula", formula_data.get("formula", content or ""))) or None
    safe_metadata = {
        key: _primitive(raw[key])
        for key in ("block_id", "block_order")
        if key in raw and isinstance(_primitive(raw[key]), (str, int, float, bool, type(None)))
    }
    return DocumentElement(
        id=f"page-{page_index}-element-{block_id}",
        type=block_type,
        text=str(content) if content is not None else None,
        confidence=float(raw["score"]) if isinstance(raw.get("score"), (int, float)) else None,
        bbox=[item for item in _primitive(bbox)]
        if isinstance(bbox, Sequence) and not isinstance(bbox, (str, bytes))
        else None,
        polygon=_polygon(raw.get("polygon")),
        reading_order=int(raw.get("block_order", raw.get("order", fallback_order))),
        html=_table_html(table),
        table=table,
        formula=formula,
        metadata=safe_metadata,
    )


def _table_html(table: dict[str, Any] | None) -> str | None:
    if not table:
        return None
    for key in ("html", "pred_html", "table_html"):
        if isinstance(table.get(key), str):
            return table[key]
    return None


def _markdown(result: Any, data: Mapping[str, Any]) -> str | None:
    """Generate Markdown only for requested output modes; never write a file."""

    markdown_value = getattr(result, "markdown", None)
    if callable(markdown_value):
        markdown_value = markdown_value()
    if isinstance(markdown_value, Mapping):
        text = markdown_value.get("markdown_texts", markdown_value.get("text"))
        return str(text) if text is not None else None
    if isinstance(markdown_value, str):
        return markdown_value
    text = data.get("markdown", data.get("markdown_texts"))
    return str(text) if isinstance(text, str) else None
