from fpdf import FPDF
import os

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Texto en Braille", 0, 1, "C")
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

    def download_braille(self, text, file_path):
        # Agregar una página
        self.add_page()

        # Agregar la fuente Unicode (DejaVu Sans)
        self.add_font("DejaVu", "", "./resources/DejaVuSans.ttf", uni=True)

        # Establecer fuente DejaVu Sans
        self.set_font("DejaVu", size=16)

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
