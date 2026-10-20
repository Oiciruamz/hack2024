"""Extracción de texto de PDF vía Mistral OCR (mistral-ocr-latest).

API: https://docs.mistral.ai/api/endpoint/ocr
Docs: https://docs.mistral.ai/capabilities/document_ai/basic_ocr
"""

from __future__ import annotations

import base64
import os
import re
import time
from typing import Any, Dict, List
import requests

try:
    from mistralai.client import Mistral
except Exception:
    Mistral = None

# Alias oficial que apunta al último modelo OCR de Mistral
OCR_MODEL = "mistral-ocr-latest"
_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 5
_IMAGE_MD_RE = re.compile(r"!\[.*?\]\(.*?\)")
_TABLE_PLACEHOLDER_RE = re.compile(r"\[tbl-\d+\.(?:html|md)\]\(tbl-\d+\.(?:html|md)\)")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


class MistralOCRError(Exception):
    """Error al llamar o procesar la respuesta de Mistral OCR."""


def _require_api_key() -> str:
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        raise MistralOCRError(
            "Falta MISTRAL_API_KEY. Copia .env.example a .env y configura tu API key."
        )
    return api_key


def _pdf_to_data_url(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:application/pdf;base64,{encoded}"


def _parse_markdown_table_rows(table_lines: List[str]) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in table_lines:
        stripped = line.strip()
        if _TABLE_SEP_RE.match(stripped):
            continue
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows


def _format_table_accessible(table_cells: List[List[str]]) -> List[str]:
    if not table_cells:
        return []

    # Extraer encabezados de la fila 1
    raw_headers = table_cells[0]
    headers = [
        " ".join(h.split()) if h.strip() else f"Columna {idx}"
        for idx, h in enumerate(raw_headers, start=1)
    ]
    num_cols = len(headers)

    lines = [f"[INICIO DE TABLA: {num_cols} columnas]"]

    # Si la tabla solo contiene la fila de encabezados
    if len(table_cells) == 1:
        for idx, h in enumerate(headers, start=1):
            lines.append(f"- Columna {idx}: {h}")
        lines.append("[FIN DE TABLA]")
        return lines

    # Filas de datos
    for row_idx, row in enumerate(table_cells[1:], start=1):
        lines.append(f"Fila {row_idx}:")
        for col_idx, header in enumerate(headers):
            val = row[col_idx].strip() if col_idx < len(row) and row[col_idx] else ""
            clean_val = " ".join(val.split()) if val else "(vacio)"
            lines.append(f"- {header}: {clean_val}")

    lines.append("[FIN DE TABLA]")
    return lines



def _html_table_to_cells(html: str) -> List[List[str]]:
    """Convierte una tabla HTML simple (respuesta OCR) a filas/celdas."""
    rows: List[List[str]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.I | re.S):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.I | re.S)
        cleaned = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if cleaned:
            rows.append(cleaned)
    return rows


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def markdown_to_lines(markdown: str) -> List[str]:
    """Convierte markdown de OCR a líneas de texto plano (tablas accesibles)."""
    cleaned = _IMAGE_MD_RE.sub("", markdown)
    cleaned = _TABLE_PLACEHOLDER_RE.sub("", cleaned)
    raw_lines = cleaned.splitlines()
    result: List[str] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if _is_table_line(line):
            table_block = []
            while i < len(raw_lines) and (
                _is_table_line(raw_lines[i]) or not raw_lines[i].strip()
            ):
                if raw_lines[i].strip():
                    table_block.append(raw_lines[i])
                i += 1
            cells = _parse_markdown_table_rows(table_block)
            if cells:
                result.extend(_format_table_accessible(cells))
            continue

        stripped = line.strip()
        if stripped:
            stripped = re.sub(r"^#{1,6}\s+", "", stripped)
            stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
            result.append(stripped)
        else:
            result.append("")
        i += 1

    compact: List[str] = []
    prev_blank = False
    for line in result:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        compact.append(line)
        prev_blank = is_blank
    return compact


def _page_to_lines(page) -> List[str]:
    """Une markdown de página + tablas extraídas (si vienen aparte)."""
    if isinstance(page, dict):
        md = page.get("markdown") or ""
        tables = page.get("tables") or []
    else:
        md = getattr(page, "markdown", None) or ""
        tables = getattr(page, "tables", None) or []

    lines = markdown_to_lines(md)

    for table in tables:
        content = None
        if isinstance(table, dict):
            content = table.get("content") or table.get("markdown") or table.get("html")
        else:
            content = (
                getattr(table, "content", None)
                or getattr(table, "markdown", None)
                or getattr(table, "html", None)
            )
        if not content:
            continue
        content_str = str(content).strip()
        if content_str.startswith("<"):
            cells = _html_table_to_cells(content_str)
            if cells:
                lines.append("")
                lines.extend(_format_table_accessible(cells))
        elif "|" in content_str:
            lines.append("")
            lines.extend(markdown_to_lines(content_str))
    return lines


def extract_text_from_pdf(pdf_path: str) -> List[str]:
    """
    Extrae texto de un PDF con Mistral OCR (mistral-ocr-latest).

    Returns:
        Lista de líneas de texto (mismo contrato que count_text_lines).
    """
    api_key = _require_api_key()
    document_url = _pdf_to_data_url(pdf_path)

    url = "https://api.mistral.ai/v1/ocr"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": OCR_MODEL,
        "document": {
            "type": "document_url",
            "document_url": document_url,
        },
    }

    last_error: Exception | None = None
    pages: List[Any] = []

    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            if resp.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_BASE_SECONDS * (attempt + 1))
                    continue
                raise MistralOCRError(
                    "Rate limit excedido (429) en Mistral OCR. Intenta nuevamente en unos segundos."
                )

            if resp.status_code != 200:
                raise MistralOCRError(
                    f"Mistral OCR error HTTP {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            pages = data.get("pages") or []
            break
        except MistralOCRError:
            raise
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            is_rate_limited = (
                "429" in message or "rate_limited" in message or "rate limit" in message
            )
            if is_rate_limited and attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BASE_SECONDS * (attempt + 1))
                continue
            raise MistralOCRError(f"Error al llamar a Mistral OCR: {exc}") from exc

    if not pages:
        if last_error:
            raise MistralOCRError(f"Error al llamar a Mistral OCR: {last_error}")
        raise MistralOCRError("Mistral OCR no devolvió páginas de texto.")

    all_lines: List[str] = []
    for page in pages:
        page_lines = _page_to_lines(page)
        if page_lines:
            if all_lines and all_lines[-1].strip():
                all_lines.append("")
            all_lines.extend(page_lines)

    if not any(line.strip() for line in all_lines):
        raise MistralOCRError("Mistral OCR no extrajo texto del documento.")

    return all_lines


def clean_markdown_and_invisibles(text: str) -> str:
    """
    Sanitiza el texto eliminando sintaxis visual de Markdown (negritas, cursivas,
    bloques) y caracteres invisibles o incompatibles con Braille plano,
    preservando intacta la estructura de tablas accesibles.
    """
    if not text:
        return ""

    # 1. Caracteres invisibles y saltos no convencionales
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\u00ad", "")
    text = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")

    # 2. Caracteres tipográficos comunes
    text = text.replace("«", "“").replace("»", "”")
    text = text.replace("•", "-").replace("·", "-").replace("–", "-")

    # 3. Limpiar Markdown visual
    # Negrita: **palabra** o __palabra__
    text = re.sub(r"\*\*([^*]+?)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+?)__", r"\1", text)

    # Cursiva: *palabra* o _palabra_
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\n]+?)_(?!_)", r"\1", text)

    # Tachado: ~~palabra~~
    text = re.sub(r"~~([^~]+?)~~", r"\1", text)

    # Código en línea: `código`
    text = re.sub(r"`([^`]+?)`", r"\1", text)

    # Viñetas con asterisco al inicio de línea: '* texto' -> '- texto'
    text = re.sub(r"^\s*\*\s+", "- ", text, flags=re.MULTILINE)

    # Cualquier asterisco residual huérfano
    text = text.replace("*", "")

    # Normalizar espacios múltiples por línea y evitar múltiples líneas vacías consecutivas
    lines = []
    prev_blank = False
    for line in text.split("\n"):
        clean_line = " ".join(line.split())
        is_blank = not clean_line
        if is_blank and prev_blank:
            continue
        lines.append(clean_line)
        prev_blank = is_blank

    return "\n".join(lines).strip()


def refine_text_with_ai(text: str) -> str:
    """
    Revisa y valida la coherencia del texto post-OCR utilizando Mistral Chat.
    Corrige erratas de escaneo y une saltos de línea anómalos manteniendo
    estrictamente la estructura de tablas accesibles.
    """
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        return text

    system_prompt = (
        "Eres un asistente experto en accesibilidad y transcripción a Braille.\n"
        "Tu tarea es revisar el texto extraído por OCR de un documento para corregir "
        "la coherencia sintáctica y eliminar artefactos de formato y escaneo.\n"
        "Reglas obligatorias:\n"
        "1. Elimina cualquier marca de formato Markdown visual como negritas (**texto** -> texto) "
        "o cursivas (*texto* -> texto).\n"
        "2. Corrige erratas evidentes de OCR y une palabras cortadas artificialmente.\n"
        "3. Conserva el signo '+' tal cual cuando sea parte de combinaciones de teclas (ej. 'Ctrl + E') "
        "o expresiones matemáticas.\n"
        "4. REGLA CRÍTICA: Conserva INTACTOS los bloques de tablas: '[INICIO DE TABLA: ...]' y '[FIN DE TABLA]', "
        "así como sus filas 'Fila X:' y pares '- Encabezado: Valor'. NO cambies esa estructura.\n"
        "5. Devuelve ÚNICAMENTE el texto corregido, sin notas, sin saludos ni delimitadores de código markdown."
    )

    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices") or []
            if choices:
                refined = choices[0].get("message", {}).get("content", "")
                if refined and refined.strip():
                    clean_refined = re.sub(r"^```[a-zA-Z]*\n?", "", refined.strip())
                    clean_refined = re.sub(r"\n?```$", "", clean_refined)
                    return clean_refined.strip()
    except Exception as exc:
        print(f"[Aviso Refinamiento IA] No se pudo conectar con Mistral Chat: {exc}. Usando sanitización local.")

    return text


def clean_and_refine_for_braille(text: str, use_ai: bool = True) -> str:
    """
    Procesa el texto para dejarlo 100% fidedigno y compatible con Braille:
    1. Si use_ai es True, solicita revisión de coherencia a Mistral AI.
    2. Aplica sanitización determinista de Markdown y caracteres invisibles.
    """
    if use_ai:
        text = refine_text_with_ai(text)
    return clean_markdown_and_invisibles(text)

