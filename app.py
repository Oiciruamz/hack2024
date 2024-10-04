from flask import Flask, render_template, request, send_file
import pytesseract
from app import main as mn
from pdf2image import convert_from_path
# from app.pdfDown import PDF, create_pdf
from app.pdfDown import PDF
import LetrasInclusivas as lt
import os

app = Flask(__name__)

# Ruta principal para la página de inicio
@app.route('/')
def index():
    return render_template('index.html')

# Ruta para procesar el PDF y traducirlo a Braille
@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdf_file' not in request.files:
        return 'No PDF file part', 400
    
    pdf_file = request.files['pdf_file']

    # Guardar temporalmente el PDF
    file_path = os.path.join('temp_files', 'temp_pdf.pdf')
    pdf_file.save(file_path)

    # Contar líneas de texto y procesarlas
    lines = lt.count_text_lines(file_path)
    texto = " ".join(lines)

    # Convertir a Braille
    braille = mn.user_text(texto)

    # Renderizar el resultado en la página
    return render_template('result.html', braille=braille)

@app.route('/download_braille', methods=['POST'])
def download_braille():
    text = request.form['braille']  # Obtiene el texto de braille desde el formulario
    file_path = "mi_documento_braille.pdf"

    # Crear el PDF
    pdf = PDF()
    pdf.download_braille(text, file_path)

    # Enviar el archivo para descargar
    return send_file(file_path, as_attachment=True)

# Función para contar líneas de texto en la imagen (la misma de Streamlit)
def count_text_lines(pdf_path):
    images = convert_from_path(pdf_path)
    all_lines = []

    for image in images:
        preprocessed_image = lt.preprocess_image_for_ocr(image)
        custom_config = r'--oem 3 --psm 4'
        text = pytesseract.image_to_string(preprocessed_image, lang='spa', config=custom_config)
        lines = [line for line in text.split('\n') if line.strip()]
        all_lines.extend(lines)

    return all_lines

if __name__ == '__main__':
    app.run(debug=True)