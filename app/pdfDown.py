from fpdf import FPDF
import os
import re

class PDF(FPDF):
    def header(self):
        pass

    
    def footer(self):
        pass


    def download_braille(self, text, file_path):
        # Agregar una página
        self.add_page()

        # Agregar la fuente Unicode (DejaVu Sans)
        font_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'DejaVuSans.ttf')
        font_path = os.path.abspath(font_path)

        # Compatible con fpdf2 y PyFPDF clásico
        try:
            self.add_font("DejaVu", "", font_path)
        except TypeError:
            self.add_font("DejaVu", "", font_path, uni=True)

        # Si PyFPDF cargó un archivo de cache con ruta relativa antigua, forzar ruta absoluta
        if hasattr(self, 'fonts') and isinstance(self.fonts, dict):
            for k in list(self.fonts.keys()):
                if isinstance(self.fonts[k], dict) and 'ttffile' in self.fonts[k]:
                    self.fonts[k]['ttffile'] = font_path

        # Configurar márgenes óptimos para aprovechar toda la hoja de la impresora
        self.set_left_margin(10)
        self.set_right_margin(10)
        self.set_top_margin(10)
        self.set_auto_page_break(True, margin=10)

        # Establecer fuente DejaVu Sans
        self.set_font("DejaVu", size=20)

        # Eliminar todos los saltos de renglón para que el braille esté todo junto
        # aprovechando al máximo toda la hoja de la impresora
        clean_text = " ".join(text.split()) if text else ""

        # Agregar texto continuo con alineación a la izquierda ('L')
        self.multi_cell(0, 10, clean_text, align="L")

        # Guardar el PDF
        self.output(file_path)

def create_pdf(text, file_path):
    # Crear instancia de la clase PDF
    pdf = PDF()
    pdf.download_braille(text, file_path)

# Texto en Braille a incluir en el PDF
text = "⠠⠇⠑⠗⠁⠎ ⠊⠝⠉⠇⠥⠎⠊⠧⠁⠎"

# Ruta a la fuente DejaVu Sans TTF
font_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resources', 'DejaVuSans.ttf'))
