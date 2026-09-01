from fpdf import FPDF
import os

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
        self.add_font("DejaVu", "", font_path, uni=True)

        # Establecer fuente DejaVu Sans
        self.set_font("DejaVu", size=20)

        # Agregar texto
        self.multi_cell(0, 10, text)

        # Guardar el PDF
        self.output(file_path)

def create_pdf(text, file_path):
    # Crear instancia de la clase PDF
    pdf = PDF()
    pdf.download_braille(text, file_path)

# Texto en Braille a incluir en el PDF
text = "⠠⠇⠑⠗⠁⠎ ⠊⠝⠉⠇⠥⠎⠊⠧⠁⠎"

# Ruta a la fuente DejaVu Sans TTF
font_path = "DejaVuSans.ttf"
