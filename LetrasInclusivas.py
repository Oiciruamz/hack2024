import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path
from app.pdfDown import PDF, create_pdf


def preprocess_image(image):
    # Convertir a escala de grises
    gray_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    return gray_image


def detect_edges(gray_image, low_threshold=None, high_threshold=None):
    """
    Detecta bordes usando Canny con parámetros adecuados para documentos escaneados.
    Si no se especifican umbrales, se calculan a partir de la mediana del histograma.
    """
    # Suavizar para reducir ruido preservando bordes
    blurred = cv2.GaussianBlur(gray_image, (5, 5), 0)

    # Establecer umbrales de Canny si no se dan
    if low_threshold is None or high_threshold is None:
        v = np.median(blurred)
        sigma = 0.33
        low_threshold = int(max(0, (1.0 - sigma) * v))
        high_threshold = int(min(255, (1.0 + sigma) * v))

    edges = cv2.Canny(blurred, low_threshold, high_threshold, apertureSize=3)
    return edges


def detect_lines(gray_image, edges):
    """
    Detecta líneas usando HoughLinesP y separa líneas horizontales y verticales.
    Devuelve dos listas: horizontales y verticales (cada elemento: (x1,y1,x2,y2)).
    """
    height, width = gray_image.shape[:2]

    # Parámetros adaptativos para Hough
    rho = 1
    theta = np.pi / 180
    # Umbral de votos: reducido para no perder líneas en escaneos
    threshold = max(50, int(min(width, height) * 0.02))
    min_line_length = max(50, int(max(width, height) * 0.1))
    max_line_gap = 20

    lines_p = cv2.HoughLinesP(edges, rho, theta, threshold, minLineLength=min_line_length, maxLineGap=max_line_gap)

    horiz_lines = []
    vert_lines = []
    if lines_p is not None:
        lines_p = lines_p.reshape(-1, 4)
        for x1, y1, x2, y2 in lines_p:
            # Clasificar por orientación
            if abs(y2 - y1) <= 8:  # prácticamente horizontal
                horiz_lines.append((x1, y1, x2, y2))
            elif abs(x2 - x1) <= 8:  # prácticamente vertical
                vert_lines.append((x1, y1, x2, y2))
    return horiz_lines, vert_lines


def identify_structure(horiz_lines, vert_lines, gray_image):
    """
    Detección básica de estructuras: busca regiones rectangulares formadas por
    múltiples líneas horizontales y verticales (posibles tablas) o divisores.
    Devuelve lista de dicts con bounding boxes y tipo ('table'|'divider').

    IMPORTANTE: Las franjas de filas adyacentes se fusionan en una sola tabla
    para evitar generar estructuras duplicadas.
    """
    structures = []
    height, width = gray_image.shape[:2]

    if not horiz_lines or not vert_lines:
        return structures

    # Normalizar y ordenar
    horiz_sorted = sorted(horiz_lines, key=lambda l: (l[1] + l[3]) // 2)
    vert_sorted = sorted(vert_lines, key=lambda l: (l[0] + l[2]) // 2)

    # ── Filtrar líneas que son bordes de página ──
    # Las verticales que abarcan >50% de la altura son bordes del documento,
    # NO separadores de columnas.  Los separadores reales de una tabla solo
    # abarcan la altura de esa tabla (típicamente 10-20% de la página).
    vert_table = [v for v in vert_sorted
                  if abs(max(v[1], v[3]) - min(v[1], v[3])) < height * 0.5]

    # Si hay suficientes verticales, buscar filas de tabla
    if len(vert_table) >= 2:
        # Recolectar franjas Y donde hay al menos 2 verticales cruzando
        table_bands = []  # lista de (y_top, y_bottom)
        for i in range(len(horiz_sorted) - 1):
            y_top = (horiz_sorted[i][1] + horiz_sorted[i][3]) // 2
            y_bottom = (horiz_sorted[i + 1][1] + horiz_sorted[i + 1][3]) // 2
            if y_bottom - y_top < 10:
                continue
            
            # Contar verticales (no-borde) que cruzan este rango y tienen tamaño mínimo
            verts_in_range = 0
            for v in vert_table:
                vy_min = min(v[1], v[3])
                vy_max = max(v[1], v[3])
                if vy_min <= y_top + 5 and vy_max >= y_bottom - 5:
                    if (vy_max - vy_min) > 15:  # Evitar contar puntos o comas como verticales
                        verts_in_range += 1
                        
            if verts_in_range >= 2:
                table_bands.append((y_top, y_bottom))

        # Fusionar franjas adyacentes/superpuestas en tablas únicas
        if table_bands:
            # Calcular umbral dinámico basado en la altura mediana de las franjas
            band_heights = [yb - yt for yt, yb in table_bands]
            merge_threshold = max(int(np.median(band_heights) * 2), 50)

            merged = [[table_bands[0][0], table_bands[0][1]]]  # [y_top, y_bottom]
            for y_t, y_b in table_bands[1:]:
                prev = merged[-1]
                # Si la franja actual está dentro del umbral dinámico
                if y_t <= prev[1] + merge_threshold:
                    prev[1] = max(prev[1], y_b)
                else:
                    merged.append([y_t, y_b])

            for y_top, y_bottom in merged:
                table_h = y_bottom - y_top
                min_vert_span = max(table_h * 0.3, 20)
                
                # Recolectar X de verticales que se solapan significativamente con esta tabla
                t_verts_x = []
                for v in vert_table:
                    vy_min = min(v[1], v[3])
                    vy_max = max(v[1], v[3])
                    inter_min = max(y_top, vy_min)
                    inter_max = min(y_bottom, vy_max)
                    
                    if inter_max - inter_min >= min_vert_span:
                        t_verts_x.append((v[0] + v[2]) // 2)
                
                if not t_verts_x:
                    continue
                    
                t_verts_x = sorted(t_verts_x)
                grouped_x = []
                for x in t_verts_x:
                    if not grouped_x or x - grouped_x[-1] > 15:
                        grouped_x.append(x)
                        
                if len(grouped_x) < 2:
                    continue
                    
                # Validar que la tabla tenga un ancho razonable
                if (max(grouped_x) - min(grouped_x)) < width * 0.1:
                    continue
                    
                cols = len(grouped_x) - 1
                
                structures.append({
                    'type': 'table',
                    'bbox': (min(grouped_x), y_top, max(grouped_x), y_bottom),
                    'cols': cols
                })

    # Detectar divisores largos (líneas horizontales que cruzan >60% de la página)
    for x1, y1, x2, y2 in horiz_sorted:
        line_len = abs(x2 - x1)
        if line_len > width * 0.6:
            # No agregar divisores que caigan dentro de una tabla ya detectada
            mid_y = (y1 + y2) // 2
            inside_table = any(
                s['type'] == 'table' and s['bbox'][1] <= mid_y <= s['bbox'][3]
                for s in structures
            )
            if not inside_table:
                structures.append({'type': 'divider', 'bbox': (min(x1, x2), y1, max(x1, x2), y2)})

    return structures


def segment_table_cells(gray_image, table_bbox, horiz_lines, vert_lines, expected_cols=None):
    """
    Dado `gray_image` (numpy array) y un bbox de tabla (x_min,y_top,x_max,y_bottom),
    devuelve una lista ordenada por filas de cajas de celdas (x1,y1,x2,y2).
    Si faltan verticales se intenta estimar columnas iguales usando `expected_cols`.
    """
    x_min, y_top, x_max, y_bottom = table_bbox
    table_height = y_bottom - y_top
    min_vert_span = max(table_height * 0.3, 20)  # mínimo 30% de la tabla o 20px

    # Filtrar verticales: deben estar dentro del bbox X, solapar en Y y abarcar suficiente altura
    # (esto descarta líneas cortas de bordes de caracteres/artefactos)
    qualified_verts = []
    for v in vert_lines:
        vx = (v[0] + v[2]) // 2
        vy_min = min(v[1], v[3])
        vy_max = max(v[1], v[3])
        if vx >= x_min - 5 and vx <= x_max + 5:
            inter_min = max(y_top, vy_min)
            inter_max = min(y_bottom, vy_max)
            if inter_max - inter_min >= min_vert_span:
                qualified_verts.append(v)
    vert_x_raw = sorted([(v[0] + v[2]) // 2 for v in qualified_verts])

    # Fusionar coordenadas X cercanas (< 15px) que son la misma línea detectada 2 veces
    vert_x = []
    for x in vert_x_raw:
        if not vert_x or x - vert_x[-1] > 15:
            vert_x.append(x)

    # incluir bordes de la tabla
    if len(vert_x) == 0:
        vert_x = [x_min, x_max]
    else:
        if vert_x[0] > x_min + 2:
            vert_x.insert(0, x_min)
        if vert_x[-1] < x_max - 2:
            vert_x.append(x_max)

    # si hay menos columnas que se esperan, estimar division equitativa
    if expected_cols and len(vert_x) - 1 < expected_cols:
        step = (x_max - x_min) // expected_cols
        vert_x = [x_min + i * step for i in range(expected_cols + 1)]

    # líneas horizontales en el rango
    table_width = x_max - x_min
    
    fragments = []
    for h in horiz_lines:
        hy = (h[1] + h[3]) // 2
        hx_min = min(h[0], h[2])
        hx_max = max(h[0], h[2])
        if hy >= y_top - 5 and hy <= y_bottom + 5:
            inter_min = max(x_min, hx_min)
            inter_max = min(x_max, hx_max)
            if inter_max > inter_min:
                fragments.append({'y': hy, 'xmin': inter_min, 'xmax': inter_max})
                
    fragments.sort(key=lambda x: x['y'])
    
    horiz_y_raw = []
    if fragments:
        current_band_y = fragments[0]['y']
        current_intervals = [(fragments[0]['xmin'], fragments[0]['xmax'])]
        
        for f in fragments[1:]:
            if f['y'] - current_band_y <= 15:
                current_intervals.append((f['xmin'], f['xmax']))
            else:
                current_intervals.sort(key=lambda x: x[0])
                merged_intervals = [list(current_intervals[0])]
                for interval in current_intervals[1:]:
                    if interval[0] <= merged_intervals[-1][1]:
                        merged_intervals[-1][1] = max(merged_intervals[-1][1], interval[1])
                    else:
                        merged_intervals.append(list(interval))
                
                total_coverage = sum(i[1] - i[0] for i in merged_intervals)
                if total_coverage >= table_width * 0.5:
                    horiz_y_raw.append(current_band_y)
                    
                current_band_y = f['y']
                current_intervals = [(f['xmin'], f['xmax'])]
                
        current_intervals.sort(key=lambda x: x[0])
        merged_intervals = [list(current_intervals[0])]
        for interval in current_intervals[1:]:
            if interval[0] <= merged_intervals[-1][1]:
                merged_intervals[-1][1] = max(merged_intervals[-1][1], interval[1])
            else:
                merged_intervals.append(list(interval))
        
        total_coverage = sum(i[1] - i[0] for i in merged_intervals)
        if total_coverage >= table_width * 0.5:
            horiz_y_raw.append(current_band_y)
            
    horiz_y = horiz_y_raw

    if len(horiz_y) == 0:
        horiz_y = [y_top, y_bottom]
    else:
        if horiz_y[0] > y_top + 10:
            horiz_y.insert(0, y_top)
        if horiz_y[-1] < y_bottom - 10:
            horiz_y.append(y_bottom)

    # construir celdas por rejilla
    cells = []
    for r in range(len(horiz_y) - 1):
        row = []
        y1 = int(horiz_y[r])
        y2 = int(horiz_y[r+1])
        if y2 - y1 <= 2:
            continue
        for c in range(len(vert_x) - 1):
            x1 = int(vert_x[c])
            x2 = int(vert_x[c+1])
            if x2 - x1 <= 2:
                continue
            # Recortar hacia ADENTRO para excluir las líneas negras del borde
            pad = 5
            xa = x1 + pad
            xb = x2 - pad
            ya = y1 + pad
            yb = y2 - pad
            if xb <= xa or yb <= ya:
                xa, xb, ya, yb = x1, x2, y1, y2
            row.append((xa, ya, xb, yb))
        if row:
            cells.append(row)
    return cells


def ocr_table_cells_from_page(pil_image, gray_image=None, tesseract_config=r'--oem 3 --psm 6'):
    """
    Detecta tablas en la página, segmenta en celdas y devuelve texto por celda.
    Retorna una lista de tablas; cada tabla es lista de filas; cada fila es lista de strings.
    """
    if gray_image is None:
        gray_image = preprocess_image(pil_image)

    edges = detect_edges(gray_image)
    horiz_lines, vert_lines = detect_lines(gray_image, edges)
    structures = identify_structure(horiz_lines, vert_lines, gray_image)

    tables_text = []
    for s in structures:
        if s.get('type') != 'table':
            continue
        bbox = s.get('bbox')
        expected_cols = s.get('cols')
        cells = segment_table_cells(gray_image, bbox, horiz_lines, vert_lines, expected_cols=expected_cols)
        table_text = []
        for row in cells:
            row_text = []
            for (x1, y1, x2, y2) in row:
                crop = gray_image[y1:y2, x1:x2]
                # verificar recorte válido
                if crop is None or crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
                    text = ''
                else:
                    # mejorar legibilidad antes de OCR
                    crop_resized = resize_image(crop, scale=2)
                    # asegurar tipo uint8
                    crop_uint8 = np.asarray(crop_resized).astype(np.uint8)
                    try:
                        text = pytesseract.image_to_string(crop_uint8, lang='spa', config=tesseract_config)
                    except Exception:
                        text = ''
                row_text.append(text.strip())
            table_text.append(row_text)
        tables_text.append({'bbox': bbox, 'cells': table_text})
    return tables_text


def binarize_image(gray_image):
    # Aplicar un umbral binario para que el fondo sea blanco y el texto negro
    _, binarized_image = cv2.threshold(gray_image, 150, 255, cv2.THRESH_BINARY)
    return binarized_image

def remove_noise(image):
    # Aplicar un filtro mediano para eliminar ruido
    denoised_image = cv2.medianBlur(image, 3)
    return denoised_image

def apply_dilation(image):
    kernel = np.ones((1, 1), np.uint8)
    dilated_image = cv2.dilate(image, kernel, iterations=1)
    return dilated_image

def resize_image(image, scale=2):
    # Cambiar el tamaño de la imagen para hacerla más grande
    width = int(image.shape[1] * scale)
    height = int(image.shape[0] * scale)
    resized_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
    return resized_image

def preprocess_image_for_ocr(image):
    # Convertir a escala de grises
    gray_image = preprocess_image(image)
    # Etapa nueva: detectar bordes y líneas para identificar estructura geométrica
    edges = detect_edges(gray_image)
    horiz_lines, vert_lines = detect_lines(gray_image, edges)
    structures = identify_structure(horiz_lines, vert_lines, gray_image)

    # Aplicar umbral binario
    binarized_image = binarize_image(gray_image)
    # Reducir ruido
    denoised_image = remove_noise(binarized_image)
    # Aplicar dilatación
    dilated_image = apply_dilation(denoised_image)
    # Redimensionar para mejor legibilidad
    resized_image = resize_image(dilated_image)

    # Devolvemos la imagen lista para OCR y la información estructural detectada
    return resized_image, structures

# ---------------------------------------------------------------------------
# Funciones auxiliares para la orquestación de tablas + texto general
# ---------------------------------------------------------------------------

def _format_table_accessible(table_cells):
    """
    Formatea las celdas de una tabla en texto accesible para Braille.

    Args:
        table_cells: lista de filas, cada fila es lista de strings.

    Returns:
        Lista de líneas con el formato accesible:
            [INICIO DE TABLA]
            Fila 1, Columna 1: ...
            [FIN DE TABLA]
    """
    lines = ["[INICIO DE TABLA]"]
    for row_idx, row in enumerate(table_cells, start=1):
        for col_idx, cell_text in enumerate(row, start=1):
            # Limpiar espacios extra / saltos internos de la celda
            clean = " ".join(cell_text.split()) if cell_text else ""
            lines.append(f"Fila {row_idx}, Columna {col_idx}: {clean}")
    lines.append("[FIN DE TABLA]")
    return lines


def _mask_regions(gray_image, bboxes):
    """
    Dibuja rectángulos blancos (fill) sobre las regiones indicadas para que
    el OCR general no vuelva a leer el contenido de esas zonas.

    Args:
        gray_image: imagen en escala de grises (numpy array, se modifica in-place).
        bboxes:     lista de tuplas (x_min, y_top, x_max, y_bottom).

    Returns:
        La imagen con las regiones enmascaradas en blanco (255).
    """
    masked = gray_image.copy()
    for (x_min, y_top, x_max, y_bottom) in bboxes:
        cv2.rectangle(masked, (x_min, y_top), (x_max, y_bottom), 255, thickness=-1)
    return masked


# ---------------------------------------------------------------------------
# Función principal de orquestación (reemplaza a la antigua count_text_lines)
# ---------------------------------------------------------------------------

def _ocr_table_cells_batched(gray_image, cells):
    """
    OCR por lotes: apila todas las celdas de una tabla en una sola imagen
    vertical separadas por líneas blancas, ejecuta UN solo llamado a Tesseract
    y reparte el resultado por celda usando un separador especial.

    Args:
        gray_image: imagen en escala de grises de la página completa.
        cells:      lista de filas, cada fila es lista de (x1,y1,x2,y2).

    Returns:
        Lista de filas con textos: [[str, str, ...], ...]
    """
    SEPARATOR_H = 30  # altura del espacio blanco entre celdas
    flat_cells = []    # lista plana de (row_idx, col_idx, crop)
    for r_idx, row in enumerate(cells):
        for c_idx, (x1, y1, x2, y2) in enumerate(row):
            crop = gray_image[y1:y2, x1:x2]
            if crop is None or crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
                flat_cells.append((r_idx, c_idx, None))
            else:
                flat_cells.append((r_idx, c_idx, crop))

    # Si no hay celdas válidas, devolver vacío
    valid = [(r, c, cr) for r, c, cr in flat_cells if cr is not None]
    if not valid:
        return [['' for _ in row] for row in cells]

    # Determinar ancho máximo para apilar
    max_w = max(cr.shape[1] for _, _, cr in valid)

    strips = []
    for _, _, cr in valid:
        # Pad para igualar ancho
        h, w = cr.shape[:2]
        if w < max_w:
            pad = np.full((h, max_w - w), 255, dtype=np.uint8)
            cr = np.hstack([cr, pad])
        strips.append(cr)
        # Separador blanco
        strips.append(np.full((SEPARATOR_H, max_w), 255, dtype=np.uint8))

    stacked = np.vstack(strips)
    stacked_resized = resize_image(stacked, scale=2)
    stacked_uint8 = np.asarray(stacked_resized).astype(np.uint8)

    try:
        raw = pytesseract.image_to_string(
            stacked_uint8, lang='spa', config=r'--oem 3 --psm 6',
        )
    except Exception:
        raw = ''

    # Dividir resultado: cada celda genera un bloque de texto separado por
    # líneas vacías (el separador blanco las provoca).
    chunks = raw.split('\n\n')
    # Limpiar cada chunk
    chunks = [c.strip().replace('\n', ' ') for c in chunks if c.strip()]

    # Reconstruir matriz de resultados
    result = [['' for _ in row] for row in cells]
    valid_idx = 0
    for r, c, cr in flat_cells:
        if cr is None:
            result[r][c] = ''
        else:
            result[r][c] = chunks[valid_idx] if valid_idx < len(chunks) else ''
            valid_idx += 1

    return result


def count_text_lines(pdf_path):
    """
    Procesa cada página de un PDF ejecutando el flujo completo:

    1. Detecta tablas y las extrae celda por celda en formato accesible.
    2. Enmascara (mask) las tablas en la imagen para evitar duplicados.
    3. Aplica OCR al texto general (imagen enmascarada).
    4. Ensambla tablas y párrafos en orden de arriba a abajo (coordenada Y).

    Returns:
        Lista de líneas de texto listas para convertir a Braille.
    """
    print(f"[Braille] Convirtiendo PDF a imágenes: {pdf_path}")
    images = convert_from_path(pdf_path)
    total_pages = len(images)
    print(f"[Braille] {total_pages} página(s) detectada(s).")
    all_lines = []

    for page_num, image in enumerate(images, start=1):
        print(f"[Braille] --- Procesando página {page_num}/{total_pages} ---")

        # --- Paso 0: Pre-procesar ---
        print(f"[Braille]   Paso 0: Pre-procesando imagen...")
        gray_image = preprocess_image(image)
        edges = detect_edges(gray_image)
        horiz_lines, vert_lines = detect_lines(gray_image, edges)
        structures = identify_structure(horiz_lines, vert_lines, gray_image)

        table_structs = [s for s in structures if s.get('type') == 'table']
        print(f"[Braille]   Detección: {len(table_structs)} tabla(s), "
              f"{len(structures) - len(table_structs)} divisor(es).")

        # ---------------------------------------------------------------
        # Paso 1: Extraer tablas con formato accesible
        # ---------------------------------------------------------------
        page_blocks = []
        table_bboxes = []

        for t_idx, s in enumerate(table_structs, start=1):
            bbox = s['bbox']  # (x_min, y_top, x_max, y_bottom)
            expected_cols = s.get('cols')

            print(f"[Braille]   Paso 1: Extrayendo tabla {t_idx}/{len(table_structs)} "
                  f"(bbox={bbox}, cols≈{expected_cols})...")

            # Segmentar celdas
            cells = segment_table_cells(
                gray_image, bbox, horiz_lines, vert_lines,
                expected_cols=expected_cols,
            )

            total_cells = sum(len(row) for row in cells)
            print(f"[Braille]     {len(cells)} fila(s), {total_cells} celda(s) → OCR celda por celda...")

            # OCR celda por celda (preciso y rápido con pocas celdas)
            table_text_rows = []
            for row in cells:
                row_texts = []
                for (x1, y1, x2, y2) in row:
                    crop = gray_image[y1:y2, x1:x2]
                    if crop is None or crop.size == 0 or crop.shape[0] == 0 or crop.shape[1] == 0:
                        cell_text = ''
                    else:
                        crop_resized = resize_image(crop, scale=2)
                        crop_uint8 = np.asarray(crop_resized).astype(np.uint8)
                        try:
                            cell_text = pytesseract.image_to_string(
                                crop_uint8, lang='spa',
                                config=r'--oem 3 --psm 6',
                            )
                        except Exception:
                            cell_text = ''
                    row_texts.append(cell_text.strip())
                table_text_rows.append(row_texts)

            # Formatear la tabla de forma accesible
            formatted = _format_table_accessible(table_text_rows)

            page_blocks.append({
                'y': bbox[1],
                'type': 'table',
                'lines': formatted,
            })
            table_bboxes.append(bbox)

        # ---------------------------------------------------------------
        # Paso 2: Enmascarar tablas en la imagen
        # ---------------------------------------------------------------
        if table_bboxes:
            print(f"[Braille]   Paso 2: Enmascarando {len(table_bboxes)} región(es) de tabla...")
            masked_gray = _mask_regions(gray_image, table_bboxes)
        else:
            masked_gray = gray_image

        # Preprocesar la imagen enmascarada para mejorar OCR general
        binarized = binarize_image(masked_gray)
        denoised = remove_noise(binarized)
        dilated = apply_dilation(denoised)
        resized = resize_image(dilated)

        # ---------------------------------------------------------------
        # Paso 3: OCR del texto general (sin tablas) — UNA sola pasada
        # ---------------------------------------------------------------
        print(f"[Braille]   Paso 3: OCR del texto general (image_to_data)...")
        custom_config = r'--oem 3 --psm 4'

        try:
            ocr_data = pytesseract.image_to_data(
                resized, lang='spa', config=custom_config,
                output_type=pytesseract.Output.DICT,
            )
        except Exception:
            ocr_data = None

        if ocr_data is not None:
            # Agrupar texto por bloques de Tesseract para conservar el orden Y
            block_map = {}  # block_num -> {'y': ..., 'words': {}}
            n = len(ocr_data['text'])
            for i in range(n):
                txt = ocr_data['text'][i].strip()
                if not txt:
                    continue
                block_num = ocr_data['block_num'][i]
                # Coordenada Y ÷ escala (2) para volver a coords originales
                y_coord = ocr_data['top'][i] // 2
                if block_num not in block_map:
                    block_map[block_num] = {'y': y_coord, 'words': {}}
                else:
                    block_map[block_num]['y'] = min(block_map[block_num]['y'], y_coord)

                line_num = ocr_data['line_num'][i]
                key = (block_num, line_num)
                if key not in block_map[block_num]['words']:
                    block_map[block_num]['words'][key] = []
                block_map[block_num]['words'][key].append(txt)

            for block_num, bdata in block_map.items():
                block_lines = []
                for key in sorted(bdata['words'].keys()):
                    line_str = " ".join(bdata['words'][key])
                    if line_str.strip():
                        block_lines.append(line_str.strip())
                if block_lines:
                    page_blocks.append({
                        'y': bdata['y'],
                        'type': 'text',
                        'lines': block_lines,
                    })

            print(f"[Braille]     {len(block_map)} bloque(s) de texto extraído(s).")
        else:
            # Fallback: image_to_string sin coordenadas
            print(f"[Braille]     image_to_data falló, usando fallback image_to_string...")
            try:
                general_text = pytesseract.image_to_string(
                    resized, lang='spa', config=custom_config,
                )
            except Exception:
                general_text = ''
            plain_lines = [l for l in general_text.split('\n') if l.strip()]
            if plain_lines:
                page_blocks.append({
                    'y': 0,
                    'type': 'text',
                    'lines': plain_lines,
                })

        # ---------------------------------------------------------------
        # Paso 4: Ensamblar en orden de arriba a abajo (coordenada Y)
        # ---------------------------------------------------------------
        page_blocks.sort(key=lambda b: b['y'])
        page_line_count = sum(len(b['lines']) for b in page_blocks)
        for block in page_blocks:
            all_lines.extend(block['lines'])

        print(f"[Braille]   Paso 4: Página {page_num} completa → "
              f"{page_line_count} líneas ensambladas.")

    print(f"[Braille] ✓ Procesamiento terminado: {len(all_lines)} líneas totales.")
    return all_lines
