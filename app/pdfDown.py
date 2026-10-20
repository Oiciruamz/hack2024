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

        # Establecer fuente DejaVu Sans
        self.set_font("DejaVu", size=20)

        # Limpiar texto y saltos vacíos excesivos
        clean_text = text.strip() if text else ""
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)

        # Agregar texto con alineación a la izquierda ('L') para evitar que se justifique
        # y genere espacios en blanco gigantes entre palabras
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
