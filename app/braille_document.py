"""Manejo de documentos estructurados OCR, bloques, paginación y
serialización BRF (Braille ASCII) según estándares internacionales.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Tabla estándar internacional de Braille ASCII (BANA / 64 celdas)
# Índice en la cadena corresponde exactamente al offset Unicode (ord(c) - 0x2800).
# Donde los bits de puntos braille son:
# Bit 0 = punto 1, Bit 1 = punto 2, Bit 2 = punto 3,
# Bit 3 = punto 4, Bit 4 = punto 5, Bit 5 = punto 6.
BRAILLE_ASCII_BY_UNICODE_OFFSET = (
    " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y="
)

# Mapa inverso: de caracter Braille ASCII al caracter Unicode Braille correspondiente
UNICODE_BY_BRAILLE_ASCII = {
    ch: chr(0x2800 + idx)
    for idx, ch in enumerate(BRAILLE_ASCII_BY_UNICODE_OFFSET)
}


def unicode_to_braille_ascii(braille_unicode: str) -> str:
    """Convierte texto en Braille Unicode (U+2800 - U+283F) a Braille ASCII estándar (.brf).
    
    Preserva saltos de línea y espacios. Los saltos de línea se normalizan a CRLF (\\r\\n),
    que es el estándar requerido por impresoras (embossers) y software lector de archivos .brf.
    """
    if not braille_unicode:
        return ""

    out: List[str] = []
    # Normalizar saltos de línea primero
    normalized = braille_unicode.replace("\r\n", "\n").replace("\r", "\n")

    for ch in normalized:
        code = ord(ch)
        if 0x2800 <= code <= 0x283F:
            out.append(BRAILLE_ASCII_BY_UNICODE_OFFSET[code - 0x2800])
        elif ch == "\n":
            out.append("\r\n")
        elif ch in (" ", "\t"):
            out.append(ch)
        else:
            # Caracteres fuera del rango braille: si ya son ASCII imprimibles, conservarlos
            if 32 <= code <= 126:
                out.append(ch)
            else:
                out.append("?")

    res = "".join(out)
    if res and not res.endswith("\r\n"):
        res += "\r\n"
    return res


def braille_ascii_to_unicode(braille_ascii: str) -> str:
    """Convierte contenido Braille ASCII a Braille Unicode para visualización."""
    if not braille_ascii:
        return ""

    out: List[str] = []
    normalized = braille_ascii.replace("\r\n", "\n").replace("\r", "\n")
    for ch in normalized:
        if ch in UNICODE_BY_BRAILLE_ASCII:
            out.append(UNICODE_BY_BRAILLE_ASCII[ch])
        else:
            out.append(ch)
    return "".join(out)


def parse_markdown_into_blocks(text: str, page_number: int = 1) -> List[Dict[str, Any]]:
    """Descompone texto o Markdown en bloques estructurados identificables.
    
    Tipos de bloques:
    - 'table': bloques accesibles [INICIO DE TABLA...] o tablas markdown |...|
    - 'heading': encabezados (#, ##, o títulos breves en mayúsculas)
    - 'list': listas con viñetas (- , * , 1. )
    - 'paragraph': párrafos regulares de lectura
    """
    if not text:
        return []

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: List[Dict[str, Any]] = []
    block_idx = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 1. Detección de bloque de tabla accesible [INICIO DE TABLA ...]
        if re.match(r"^\[\s*INICIO\s+DE\s+TABLA", stripped, flags=re.IGNORECASE):
            table_lines = [line]
            i += 1
            while i < len(lines):
                cur = lines[i]
                table_lines.append(cur)
                if re.search(r"\[\s*FIN\s+DE\s+TABLA\s*\]", cur, flags=re.IGNORECASE):
                    i += 1
                    break
                i += 1
            content = "\n".join(table_lines).strip()
            block_idx += 1
            blocks.append({
                "id": f"p{page_number}_b{block_idx}",
                "type": "table",
                "content": content,
                "original_content": content,
                "editable": True,
            })
            continue

        # 2. Detección de tabla Markdown con pipes (| celda | celda |)
        if stripped.startswith("|") and stripped.count("|") >= 2:
            table_lines = []
            while i < len(lines) and (lines[i].strip().startswith("|") or not lines[i].strip()):
                if lines[i].strip():
                    table_lines.append(lines[i].strip())
                i += 1
            content = "\n".join(table_lines).strip()
            block_idx += 1
            blocks.append({
                "id": f"p{page_number}_b{block_idx}",
                "type": "table",
                "content": content,
                "original_content": content,
                "editable": True,
            })
            continue

        # 3. Detección de encabezado
        if stripped.startswith("#"):
            block_idx += 1
            blocks.append({
                "id": f"p{page_number}_b{block_idx}",
                "type": "heading",
                "content": stripped,
                "original_content": stripped,
                "editable": True,
            })
            i += 1
            continue

        # 4. Detección de listas
        if re.match(r"^(\*|-|\d+\.)\s+", stripped):
            list_lines = [stripped]
            i += 1
            while i < len(lines) and (re.match(r"^(\*|-|\d+\.)\s+", lines[i].strip()) or (lines[i].startswith("  ") and lines[i].strip())):
                list_lines.append(lines[i].strip())
                i += 1
            content = "\n".join(list_lines)
            block_idx += 1
            blocks.append({
                "id": f"p{page_number}_b{block_idx}",
                "type": "list",
                "content": content,
                "original_content": content,
                "editable": True,
            })
            continue

        # 5. Párrafo general (agrupar líneas contiguas hasta salto vacío)
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            next_line = lines[i].strip()
            if not next_line:
                break
            if next_line.startswith("#") or next_line.startswith("|") or re.match(r"^\[\s*INICIO\s+DE\s+TABLA", next_line, flags=re.IGNORECASE) or re.match(r"^(\*|-|\d+\.)\s+", next_line):
                break
            para_lines.append(next_line)
            i += 1

        content = " ".join(para_lines)
        block_idx += 1
        blocks.append({
            "id": f"p{page_number}_b{block_idx}",
            "type": "paragraph",
            "content": content,
            "original_content": content,
            "editable": True,
        })

    return blocks


def blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    """Reconstruye el texto continuo de una página o sección a partir de sus bloques."""
    parts = []
    for b in blocks:
        c = (b.get("content") or "").strip()
        if c:
            parts.append(c)
    return "\n\n".join(parts)


def build_document_structure(pages_raw: List[Any], filename: str) -> Dict[str, Any]:
    """Crea la estructura inmutable del documento y el estado de revisión.
    
    Acepta tanto la lista de páginas devuelta por Mistral OCR como páginas de texto plano.
    """
    pages: List[Dict[str, Any]] = []

    for idx, page in enumerate(pages_raw, start=1):
        if isinstance(page, str):
            page_text = page
            raw_md = page
        elif isinstance(page, dict):
            raw_md = page.get("markdown") or ""
            page_text = raw_md
        else:
            raw_md = getattr(page, "markdown", "") or ""
            page_text = raw_md

        blocks = parse_markdown_into_blocks(page_text, page_number=idx)
        # Si no se detectaron bloques pero hay texto:
        if not blocks and page_text.strip():
            blocks = [{
                "id": f"p{idx}_b1",
                "type": "paragraph",
                "content": page_text.strip(),
                "original_content": page_text.strip(),
                "editable": True,
            }]

        page_data = {
            "page_number": idx,
            "raw_markdown": raw_md,
            "text": blocks_to_text(blocks),
            "original_text": blocks_to_text(blocks),
            "blocks": blocks,
            "original_blocks": [dict(b) for b in blocks],
        }
        pages.append(page_data)

    if not pages:
        # Documento vacío de salvaguarda
        pages = [{
            "page_number": 1,
            "raw_markdown": "",
            "text": "",
            "original_text": "",
            "blocks": [],
            "original_blocks": [],
        }]

    return {
        "filename": filename,
        "total_pages": len(pages),
        "pages": pages,
        "original_pages": [
            {
                "page_number": p["page_number"],
                "text": p["original_text"],
                "blocks": [dict(b) for b in p["original_blocks"]],
            }
            for p in pages
        ],
    }


def document_to_full_text(doc: Dict[str, Any]) -> str:
    """Extrae el texto completo del documento uniendo todas sus páginas."""
    pages = doc.get("pages") or []
    page_texts = []
    for p in pages:
        t = (p.get("text") or "").strip()
        if not t and p.get("blocks"):
            t = blocks_to_text(p["blocks"])
        if t:
            page_texts.append(t)
    return "\n\n".join(page_texts)
