from flask import Flask, render_template, request, send_file, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
import random
import pytesseract
from app import main as mn
from pdf2image import convert_from_path
from app.pdfDown import PDF
import LetrasInclusivas as lt
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'jeje_lol'  # Cambia esto por una clave secreta real

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, email, password_hash):
        self.id = id
        self.email = email
        self.password_hash = password_hash

users = {
    'usuario@ejemplo.com': User('1', 'usuario@ejemplo.com', generate_password_hash('contraseña'))
}


@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user.id == user_id:
            return user
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users.get(email)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('inicio'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('inicio'))

@app.route('/perfil')
def perfil():
    return render_template('perfil.html')


# Ruta principal para la página de inicio
@app.route('/traducir-archivo')
def index():
    return render_template('traducir-Inicio.html')

def generar_color_pastel():
    # Genera un color pastel aleatorio
    r = random.randint(180, 255)
    g = random.randint(180, 255)
    b = random.randint(180, 255)
    return f"#{r:02x}{g:02x}{b:02x}"

@app.route('/')
def inicio():
    libros = [
        {
            "imagen": "rebelion.webp",
            "titulo": "Rebelión en la granja",
            "autor": "George Orwell"
        },
        {
            "imagen": "1984.webp",
            "titulo": "1984",
            "autor": "George Orwell"
        },
        {
            "imagen": "guerra_mundos.jpg",
            "titulo": "La guerra de los mundos",
            "autor": "H.G Wells"
        },
        {
            "imagen": "carretera.jpg",
            "titulo": "La carretera",
            "autor": "Cormac McCarthy"
        },
        {
            "imagen": "metamorfosis.jpg",
            "titulo": "La metamorfosis",
            "autor": "Franz Kakfa"
        },
        {
            "imagen": "Frankie.jpg",
            "titulo": "Frankenstein",
            "autor": "Mary Shelley"
        }
    ]
    
    # Asignar un color pastel aleatorio a cada libro
    for libro in libros:
        libro["color"] = generar_color_pastel()
    
    return render_template('inicio.html', libros=libros)

# Ruta para procesar el PDF y traducirlo a Braille
@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdf_file' not in request.files:
        return 'No PDF file part', 400
    
    pdf_file = request.files['pdf_file']

    # Crear directorio temporal si no existe
    if not os.path.exists('temp_files'):
        os.makedirs('temp_files')

    # Guardar temporalmente el PDF
    file_path = os.path.join('temp_files', 'temp_pdf.pdf')
    pdf_file.save(file_path)

    # Simular un proceso de carga largo (quitar esto en producción)
    # time.sleep(5)  # Simula que el procesamiento tarda 5 segundos

    # Contar líneas de texto y procesarlas
    lines = lt.count_text_lines(file_path)
    texto = " ".join(lines)

    # Convertir a Braille
    braille = mn.user_text(texto)

    # Renderizar el resultado en la página
    return render_template('traducir-completado.html', braille=braille)



@app.route('/registro')
def registro():
    return render_template('registro.html')

@app.route('/download_braille', methods=['POST'])
def download_braille():
    text = request.form['braille']  # Obtiene el texto de braille desde el formulario
    file_path = os.path.join('temp_files', 'mi_documento_braille.pdf')

    # Crear el PDF
    pdf = PDF()
    pdf.download_braille(text, file_path)

    # Enviar el archivo para descargar
    return send_file(file_path, as_attachment=True, download_name='braille_document.pdf')

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