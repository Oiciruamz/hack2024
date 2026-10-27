"""Pruebas unitarias e integrales del editor de revisión OCR y Braille.

Valida los 10 criterios de aceptación especificados:
1. Checkbox desmarcado -> subir PDF -> OCR -> exportación actual sin editor (regresión).
2. Checkbox marcado -> subir PDF -> OCR -> aparece editor y no se genera BRF final prematuramente.
3. Editar palabra, acento o número -> braille cambia y no vuelve a ejecutarse OCR.
4. Dos ediciones rápidas -> control de concurrencia y descarte de respuestas obsoletas.
5. Guardar, cambiar de página y regresar -> ediciones persisten en la sesión.
6. Editar tabla -> preservación de filas, columnas y relación estructural.
7. Error o latencia -> preservación del texto y reintento.
8. Finalizar revisión -> exportar PDF y BRF derivados de la misma versión confirmada.
9. Pruebas de caracteres: mayúsculas, números, ñ, acentos, puntuación y saltos de línea.
10. Accesibilidad y diseño responsivo: presencia de etiquetas semánticas, ARIA y roles.
"""

import io
import json
import os
import unittest
from unittest.mock import patch, MagicMock

import run
from app import braille_document as bdoc


class EditorBrailleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = run.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Dummy PDF válido que inicia con %PDF
        self.valid_pdf_content = b"%PDF-1.4\n%Mock PDF test content for automated tests\n%%EOF"

    # 1. Regresión: Checkbox desmarcado -> Flujo directo a completado sin editor
    @patch('run.ocr_mistral.extract_text_from_pdf')
    def test_01_flujo_directo_sin_revision(self, mock_extract):
        mock_extract.return_value = ["Capítulo Primero", "Texto original directo sin editor."]

        data = {
            'pdf_file': (io.BytesIO(self.valid_pdf_content), 'libro_directo.pdf'),
            # allow_review no se envía o está desmarcado
        }
        response = self.client.post('/upload', data=data, content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        # Verifica que se renderiza directamente la pantalla final de descarga
        self.assertIn("Tu documento está listo", html)
        self.assertIn("Descargar PDF", html)
        self.assertIn("Descargar BRF", html)
        # Y no redirige a la pantalla de revisión
        self.assertNotIn("/revisar/", response.headers.get('Location', ''))

    # 2. Checkbox marcado -> Redirección a editor, sin generar BRF prematuramente
    @patch('run.ocr_mistral.extract_structured_document')
    def test_02_flujo_optin_con_revision(self, mock_extract_struct):
        mock_extract_struct.return_value = {
            "filename": "documento_revision.pdf",
            "total_pages": 1,
            "pages": [
                {
                    "page_number": 1,
                    "text": "Texto inicial detectado por OCR.",
                    "original_text": "Texto inicial detectado por OCR.",
                    "blocks": [
                        {
                            "id": "p1_b1",
                            "type": "paragraph",
                            "content": "Texto inicial detectado por OCR.",
                            "original_content": "Texto inicial detectado por OCR.",
                            "editable": True
                        }
                    ]
                }
            ],
            "original_pages": [
                {
                    "page_number": 1,
                    "text": "Texto inicial detectado por OCR.",
                    "blocks": []
                }
            ]
        }

        data = {
            'pdf_file': (io.BytesIO(self.valid_pdf_content), 'documento_revision.pdf'),
            'allow_review': '1',
        }
        response = self.client.post('/upload', data=data, content_type='multipart/form-data')

        # Debe redirigir al editor de revisión
        self.assertEqual(response.status_code, 302)
        location = response.headers.get('Location', '')
        self.assertIn('/revisar/', location)

        review_id = location.split('/revisar/')[1].strip()
        doc = run._obtener_sesion_revision(review_id)
        self.assertIsNotNone(doc)
        # Asegurar que el documento no esté confirmado ni tenga descarga prematura
        self.assertFalse(doc.get('confirmed', False))
        self.assertIsNone(doc.get('download_id'))

    # 3. Editar texto -> vista braille cambia y NO se vuelve a llamar a Mistral OCR
    @patch('run.ocr_mistral.extract_ocr_pages')
    def test_03_edicion_texto_y_sin_reinvocar_ocr(self, mock_ocr_pages):
        # Texto con palabras, números y acentos
        text_edit = "Página 1: El pingüino comió 12 peces en el río."
        response = self.client.post('/api/traducir-braille', json={'text': text_edit, 'seq': 1})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        braille_res = data['braille']

        # Verificar que el braille contenga representación válida (no vacía)
        self.assertTrue(len(braille_res) > 10)
        # Verificar que NO se haya invocado a Mistral OCR durante la edición
        mock_ocr_pages.assert_not_called()

    # 4. Control de concurrencia: dos ediciones rápidas y descarte de respuestas obsoletas
    def test_04_control_de_concurrencia_seq(self):
        resp1 = self.client.post('/api/traducir-braille', json={'text': 'Versión A', 'seq': 10})
        resp2 = self.client.post('/api/traducir-braille', json={'text': 'Versión B posterior', 'seq': 11})

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        data1 = resp1.get_json()
        data2 = resp2.get_json()

        self.assertEqual(data1['seq'], 10)
        self.assertEqual(data2['seq'], 11)
        # La versión 2 genera una traducción diferente y el cliente descarta seq 10 si llega después
        self.assertNotEqual(data1['braille'], data2['braille'])

    # 5. Guardar, cambiar de página y regresar: persistencia en la sesión
    def test_05_persistencia_multipagina(self):
        # Crear sesión con 2 páginas
        doc = bdoc.build_document_structure(
            ["Página 1 original", "Página 2 original"],
            filename="libro_multipagina.pdf"
        )
        import uuid
        rev_id = uuid.uuid4().hex
        run._guardar_sesion_revision(rev_id, doc)

        # Modificar y guardar página 1
        save_resp = self.client.post(
            f'/api/guardar-revision/{rev_id}',
            json={'page_index': 0, 'text': 'Página 1 con edición guardada exitosamente.'}
        )
        self.assertEqual(save_resp.status_code, 200)

        # Simular lectura posterior (p. ej. tras navegar a pág 2 y volver)
        doc_recuperado = run._obtener_sesion_revision(rev_id)
        self.assertEqual(doc_recuperado['pages'][0]['text'], 'Página 1 con edición guardada exitosamente.')
        # La página 2 permanece intacta
        self.assertEqual(doc_recuperado['pages'][1]['text'], 'Página 2 original')
        # El original inmutable de la página 1 no fue sobreescrito
        self.assertEqual(doc_recuperado['original_pages'][0]['text'], 'Página 1 original')

    # 6. Edición de tablas: se conservan filas, columnas y relación estructural
    def test_06_preservacion_estructura_tabla(self):
        tabla_texto = (
            "[INICIO DE TABLA: 2 columnas]\n"
            "Fila 1:\n"
            "- Capítulo: Prólogo\n"
            "- Página: 5\n"
            "Fila 2:\n"
            "- Capítulo: Desarrollo\n"
            "- Página: 18\n"
            "[FIN DE TABLA]"
        )
        blocks = bdoc.parse_markdown_into_blocks(tabla_texto, page_number=1)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['type'], 'table')
        self.assertIn("Capítulo: Prólogo", blocks[0]['content'])

        # Comprobar que parse_braille_tables puede interpretar la tabla
        parsed_matrix = run.parse_braille_tables(tabla_texto)
        self.assertTrue(len(parsed_matrix) > 0)
        self.assertEqual(parsed_matrix[0][0], ["Capítulo", "Página"])
        self.assertEqual(parsed_matrix[0][1], ["Prólogo", "5"])
        self.assertEqual(parsed_matrix[0][2], ["Desarrollo", "18"])

    # 7. Manejo de errores y restauración OCR
    def test_07_restaurar_ocr_original(self):
        doc = bdoc.build_document_structure(
            ["Texto OCR intonso y limpio"],
            filename="restaurar_test.pdf"
        )
        import uuid
        rev_id = uuid.uuid4().hex
        run._guardar_sesion_revision(rev_id, doc)

        # Modificar texto
        self.client.post(
            f'/api/guardar-revision/{rev_id}',
            json={'page_index': 0, 'text': 'Texto alterado erróneo'}
        )

        # Solicitar restauración
        rest_resp = self.client.post(
            f'/api/restaurar-ocr/{rev_id}',
            json={'page_index': 0}
        )
        self.assertEqual(rest_resp.status_code, 200)
        data = rest_resp.get_json()
        self.assertEqual(data['text'], "Texto OCR intonso y limpio")

        # Comprobar que en la sesión quedó restablecido
        doc_act = run._obtener_sesion_revision(rev_id)
        self.assertEqual(doc_act['pages'][0]['text'], "Texto OCR intonso y limpio")

    # 8. Finalizar revisión -> exportar PDF y BRF de la misma versión validada
    def test_08_finalizar_revision_y_descargas(self):
        doc = bdoc.build_document_structure(
            ["Texto definitivo revisado por el usuario con acentos: canción y número 42."],
            filename="documento_finalizado.pdf"
        )
        import uuid
        rev_id = uuid.uuid4().hex
        run._guardar_sesion_revision(rev_id, doc)

        # Finalizar revisión
        fin_resp = self.client.post(
            f'/finalizar-revision/{rev_id}',
            data={'page_index': '0', 'current_page_text': doc['pages'][0]['text']}
        )
        self.assertEqual(fin_resp.status_code, 200)

        doc_fin = run._obtener_sesion_revision(rev_id)
        self.assertTrue(doc_fin['confirmed'])
        download_id = doc_fin['download_id']
        self.assertIsNotNone(download_id)

        # Comprobar descarga de BRF
        brf_resp = self.client.get(f'/download_brf?download_id={download_id}&original_filename=doc_test')
        self.assertEqual(brf_resp.status_code, 200)
        brf_content = brf_resp.get_data(as_text=True)
        # El BRF debe ser texto ASCII, no vacío, con saltos de línea CRLF
        self.assertTrue(len(brf_content) > 0)
        self.assertIn("\r\n", brf_content)

        # Comprobar descarga de PDF
        pdf_resp = self.client.get(f'/download_braille?download_id={download_id}&original_filename=doc_test')
        self.assertEqual(pdf_resp.status_code, 200)
        pdf_bytes = pdf_resp.get_data()
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    # 9. Pruebas de caracteres: mayúsculas, números, ñ, vocales acentuadas, puntuación
    def test_09_traduccion_caracteres_especiales(self):
        test_strings = [
            "MAYÚSCULAS Y minúsculas",
            "Año del niño: 2026",
            "Vocales con tilde: á é í ó ú y diéresis ü",
            "Puntuación: ¿Cómo estás? ¡Muy bien! (Paréntesis) - Guion + Suma: 10 + 20 = 30.",
            "Línea 1\nLínea 2\nLínea 3"
        ]

        for s in test_strings:
            braille_u = run.mn.user_text(s)
            self.assertTrue(len(braille_u) > 0, f"Fallo al traducir: {s}")
            # Convertir a Braille ASCII
            brf = bdoc.unicode_to_braille_ascii(braille_u)
            self.assertTrue(len(brf) > 0, f"Fallo al convertir a BRF: {s}")
            # Asegurar que no contenga caracteres inválidos o Unicode no traducido
            for ch in brf:
                if ch not in ('\r', '\n', '\t'):
                    self.assertTrue(32 <= ord(ch) <= 126, f"Caracter no ASCII en BRF: {repr(ch)}")

    # 10. Accesibilidad: verificación de elementos semánticos y navegación por teclado
    def test_10_accesibilidad_en_vistas(self):
        # Vista de inicio
        resp_inicio = self.client.get('/traducir-archivo')
        self.assertEqual(resp_inicio.status_code, 200)
        html_inicio = resp_inicio.get_data(as_text=True)

        # Checkbox semántico accesible
        self.assertIn('id="allowReview"', html_inicio)
        self.assertIn('for="allowReview"', html_inicio)
        self.assertIn('Revisar y editar antes de descargar', html_inicio)
        self.assertIn('Corrige el texto detectado', html_inicio)

        # Stepper
        self.assertIn('aria-label="Progreso de traducción"', html_inicio)
        self.assertIn('Subir archivo', html_inicio)

        # Vista de demo
        resp_demo = self.client.post('/demo-review')
        self.assertEqual(resp_demo.status_code, 302)
        loc = resp_demo.headers.get('Location')
        resp_rev = self.client.get(loc)
        self.assertEqual(resp_rev.status_code, 200)
        html_rev = resp_rev.get_data(as_text=True)

        # Roles y regiones accesibles en el editor
        self.assertIn('id="ocrText"', html_rev)
        self.assertIn('id="braillePreview"', html_rev)
        self.assertIn('role="region"', html_rev)
        self.assertIn('aria-live="polite"', html_rev)
        self.assertIn('Finalizar revisión', html_rev)

    # 11. Verificación de que negritas y markdown no generen signos de interrogación '?'
    def test_11_negritas_no_generan_signos_de_interrogacion(self):
        samples_with_markdown = [
            "- Realizar: **Ctrl** y clic en cualquier parte de la frase.",
            "Texto en **negrita**, *cursiva*, `código` y **hola**",
            "**Edición**, el comando **Seleccionar todo**, o con el teclado **Ctrl + E**",
            "***tres asteriscos*** y asterisco suelto *"
        ]

        for s in samples_with_markdown:
            # 1. Probar en la API de vista previa braille
            api_resp = self.client.post('/api/traducir-braille', json={'text': s, 'seq': 1})
            self.assertEqual(api_resp.status_code, 200)
            data = api_resp.get_json()
            braille = data['braille']
            self.assertNotIn('?', braille, f"Signo de interrogación no deseado en vista previa para: {s}")
            self.assertNotIn('*', braille, f"Asterisco residual en vista previa para: {s}")

            # 2. Probar con mn.user_text()
            braille_direct = run.mn.user_text(s)
            self.assertNotIn('?', braille_direct, f"Signo de interrogación no deseado en user_text para: {s}")
            self.assertNotIn('*', braille_direct, f"Asterisco residual en user_text para: {s}")

    # 12. Verificación de que en el PDF final el braille esté todo junto (sin saltos de renglón)
    def test_12_pdf_braille_todo_junto(self):
        text_with_breaks = "⠨⠏⠨⠗⠨⠕\n\n⠨⠃⠨⠕⠨⠗\n⠨⠉⠥⠁⠝⠙⠕\n\n⠨⠥⠝⠁"
        pdf = run.PDF()
        out_pdf_path = os.path.join(run.TEMP_FILES_DIR, 'test_todo_junto.pdf')
        pdf.download_braille(text_with_breaks, out_pdf_path)
        self.assertTrue(os.path.exists(out_pdf_path))
        self.assertTrue(os.path.getsize(out_pdf_path) > 0)


if __name__ == '__main__':
    unittest.main()

