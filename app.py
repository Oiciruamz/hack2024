from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import random
from app import main as mn
from pdf2image import convert_from_path
from app.pdfDown import PDF
import LetrasInclusivas as lt
import requests
import os
from typing import Dict, Optional


import requests
from typing import Dict, Optional

def buscar_libros(query: str, max_results: int = 10) -> Optional[Dict]:
    """
    Busca libros en Google Books API y devuelve solo los que tienen imágenes.
    
    Args:
        query (str): Término de búsqueda
        max_results (int): Número máximo de resultados deseados con imágenes
    
    Returns:
        dict: Datos de los libros encontrados (solo con imágenes) o None si hay error
    """
    try:
        if not query:
            raise ValueError("Query es obligatorio")
            
        base_url = "https://www.googleapis.com/books/v1/volumes"
        
        # Solicitamos más resultados de los necesarios para tener margen
        # para filtrar los que no tienen imágenes
        params = {
            'q': query,
            'key': 'AIzaSyAAUx82Bb6dJvUpJ2dZnWSNsejemaXhOY8',
            'maxResults': min(40, max_results * 2),  # Pedimos el doble, máximo 40
            'fields': 'items(volumeInfo(title,authors,description,imageLinks,categories,publishedDate))',  # Optimiza la respuesta
        }
        
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if 'items' not in data:
            print("No se encontraron libros")
            return None
        
        # Filtrar solo libros con imágenes
        libros_con_imagenes = []
        for libro in data['items']:
            volumeInfo = libro.get('volumeInfo', {})
            if (volumeInfo.get('imageLinks', {}).get('thumbnail') and 
                volumeInfo.get('title') and  # Aseguramos que tenga título
                volumeInfo.get('authors')):   # Aseguramos que tenga autores
                
                # Limpiamos y estructuramos los datos
                libro_procesado = {
                    'volumeInfo': {
                        'title': volumeInfo['title'],
                        'authors': volumeInfo['authors'],
                        'description': volumeInfo.get('description', 'Descripción no disponible'),
                        'imageLinks': {
                            'thumbnail': volumeInfo['imageLinks']['thumbnail']
                        },
                        'categories': volumeInfo.get('categories', []),
                        'publishedDate': volumeInfo.get('publishedDate', '')
                    }
                }
                libros_con_imagenes.append(libro_procesado)
                
                # Si ya tenemos suficientes libros con imágenes, paramos
                if len(libros_con_imagenes) >= max_results:
                    break
        
        if not libros_con_imagenes:
            print("No se encontraron libros con imágenes")
            return None
            
        # Devolvemos en el mismo formato que la API original
        return {'items': libros_con_imagenes}
        
    except requests.exceptions.RequestException as e:
        print(f"Error en la petición HTTP: {e}")
        return None
    except ValueError as e:
        print(f"Error de validación: {e}")
        return None
    except Exception as e:
        print(f"Error inesperado: {e}")
        return None
    

def buscar_libros_categoria(categoria, max_results: int = 10) -> Optional[Dict]:
        
    try:
        if not categoria:
            raise ValueError("Query es obligatorio")
            
        base_url = "https://www.googleapis.com/books/v1/volumes"
        
        # Solicitamos más resultados de los necesarios para tener margen
        # para filtrar los que no tienen imágenes
        params = {
            'q': f'categories:{categoria}',
            'orderBy': 'relevance',
            'key': 'AIzaSyAAUx82Bb6dJvUpJ2dZnWSNsejemaXhOY8',
            'maxResults': min(40, max_results * 2),  
            'langRestrict': 'es',
            'fields': 'items(volumeInfo(title,authors,description,imageLinks,categories,publishedDate))',  # Optimiza la respuesta
        }

        response = requests.get(base_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if 'items' not in data:
            print("No se encontraron libros")
            return None
        
        # Filtrar solo libros con imágenes
        libros_con_imagenes = []
        for libro in data['items']:
            volumeInfo = libro.get('volumeInfo', {})
            if (volumeInfo.get('imageLinks', {}).get('thumbnail') and 
                volumeInfo.get('title') and  # Aseguramos que tenga título
                volumeInfo.get('authors')):   # Aseguramos que tenga autores
                
                # Limpiamos y estructuramos los datos
                libro_procesado = {
                    'volumeInfo': {
                        'title': volumeInfo['title'],
                        'authors': volumeInfo['authors'],
                        'description': volumeInfo.get('description', 'Descripción no disponible'),
                        'imageLinks': {
                            'thumbnail': volumeInfo['imageLinks']['thumbnail']
                        },
                        'categories': volumeInfo.get('categories', []),
                        'publishedDate': volumeInfo.get('publishedDate', '')
                    }
                }
                libros_con_imagenes.append(libro_procesado)
                
                # Si ya tenemos suficientes libros con imágenes, paramos
                if len(libros_con_imagenes) >= max_results:
                    break
        
        if not libros_con_imagenes:
            print("No se encontraron libros con imágenes")
            return None
            
        # Devolvemos en el mismo formato que la API original
        return {'items': libros_con_imagenes}
    
    except requests.exceptions.RequestException as e:
        print(f"Error en la petición HTTP: {e}")
        return None
    except ValueError as e:
        print(f"Error de validación: {e}")
        return None
    except Exception as e:
        print(f"Error inesperado: {e}")
        return None

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
        self.saved_books = []  


users = {
    'usuario@ejemplo.com': User('1', 'usuario@ejemplo.com', generate_password_hash('contraseña'))
}


libros = [
            {
                "id": 1,
                "imagen": "rebelion.webp",
                "titulo": "Rebelión en la granja",
                "autor": "George Orwell"
            },
            {
                "id": 2,
                "imagen": "1984.webp",
                "titulo": "1984",
                "autor": "George Orwell"
            },
            {
                "id": 3,
                "imagen": "guerra_mundos.jpg",
                "titulo": "La guerra de los mundos",
                "autor": "H.G Wells"
            },
            {
                "id": 4,
                "imagen": "carretera.jpg",
                "titulo": "La carretera",
                "autor": "Cormac McCarthy"
            },
            {
                "id": 5,
                "imagen": "metamorfosis.jpg",
                "titulo": "La metamorfosis",
                "autor": "Franz Kakfa"
            },
            {
                "id": 6,
                "imagen": "Frankie.jpg",
                "titulo": "Frankenstein",
                "autor": "Mary Shelley"
            }
        ]

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

# Almacenamiento en memoria para listas y libros
listas = {}  # Diccionario para almacenar listas
contador_listas = 1  # Contador para IDs de listas

@app.route('/crear_lista', methods=['POST'])
def crear_lista():
    global contador_listas
    data = request.get_json()
    nombre_lista = data.get('nombre')

    if not nombre_lista:
        return jsonify({'success': False, 'message': 'El nombre de la lista es requerido.'}), 400

    # Crear una nueva lista
    lista_id = contador_listas
    listas[lista_id] = {
        'id': lista_id,
        'nombre': nombre_lista,
        'libros': []
    }
    contador_listas += 1

    return jsonify({'success': True, 'message': 'Lista creada correctamente.', 'lista_id': lista_id}), 201

@app.route('/agregar_libro', methods=['POST'])
def agregar_libro():
    data = request.get_json()
    libro_id = data.get('libro_id')  # Obtener el ID del libro
    lista_id = data.get('lista_id')  # Puede ser un string, convertirlo a entero

    # Verifica que el libro y la lista existan
    if not libro_id or not lista_id:
        return jsonify({'success': False, 'message': 'El libro ID y la lista ID son requeridos.'}), 400

    try:
        lista_id = int(lista_id)

        if lista_id not in listas:
            return jsonify({'success': False, 'message': f'La lista con ID {lista_id} no existe.'}), 404

        # Agregar el libro a la lista correspondiente
        listas[lista_id]['libros'].append(libro_id)

        return jsonify({'success': True, 'message': 'Libro agregado correctamente.', 'libros': listas[lista_id]['libros']}), 201

    except ValueError:
        return jsonify({'success': False, 'message': 'El ID de la lista debe ser un número válido.'}), 400

@app.route('/listas', methods=['GET'])
def obtener_listas():
    return jsonify({'success': True, 'listas': list(listas.values())}), 200

listas_con_libros = []  # Inicializa la lista para almacenar listas con libros

@app.route('/perfil')
def perfil():

    global listas_con_libros  # Indica que estás usando la variable global

    listas_con_libros.clear()  # Limpia la lista para evitar duplicados

    # Itera sobre cada lista en el diccionario 'listas'
    for lista in listas.values():
        # Obtener los libros correspondientes a los IDs de libros en la lista
        libros_en_lista = []  # Inicializa una lista vacía para almacenar los libros
        
        # Iterar sobre los IDs de libros en la lista
        for libro_id in lista['libros']:
            # Buscar el libro en la lista de libros usando el ID (convertido a entero)
            libro_encontrado = next((libro for libro in libros if libro['id'] == int(libro_id)), None)
            if libro_encontrado:
                libros_en_lista.append(libro_encontrado)

        # Agregar la lista con los libros correspondientes
        listas_con_libros.append({
            'id': lista['id'],
            'color': generar_color_pastel(),
            'nombre': lista['nombre'],  # Nombre de la lista
            'libros': libros_en_lista     # Libros asociados a esa lista
        })

        print(listas_con_libros)  # Esto imprimirá la lista actual de listas con libros en la consola para depuración

    # Renderizar el perfil con las listas que contienen libros
    return render_template('perfil.html', listas=listas_con_libros)

@app.route('/lista/<int:lista_id>')
def lista_individual(lista_id):
    lista_seleccionada = listas.get(lista_id)

    if lista_seleccionada is None:
        return "Lista no encontrada", 404

    libros_filtrados = []

    for lista in listas_con_libros:
        if lista['id'] == lista_seleccionada['id']:
            # Solo agregar libros que estén en la lista_seleccionada
            for libro in lista['libros']:
                if str(libro['id']) in lista_seleccionada['libros']:
                    libros_filtrados.append(libro)
    
    print(libros_filtrados)
    print(lista_seleccionada)

    return render_template('lista.html', lista=lista_seleccionada, libros=libros_filtrados)


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
     # Asignar un color pastel aleatorio a cada libro
    for libro in libros:
        libro["color"] = generar_color_pastel()
    
    return render_template('inicio.html', libros=libros, listas=listas.values())

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

    # Contar líneas de texto y procesarlas
    lines = lt.count_text_lines(file_path)
    texto = " ".join(lines)

    # Convertir a Braille
    braille = mn.user_text(texto)

    # Renderizar el resultado en la página
    return render_template('traducir-completado.html', braille=braille)

@app.route('/buscar', methods=['POST'])
def buscar():
    """Ruta que procesa la búsqueda y redirecciona a los resultados"""
    query = request.form.get('query', '')
    if not query:
        return redirect(url_for('index'))
        
    resultados = buscar_libros(query)
    
    print(resultados)
    if resultados is None:
        # Manejar el error redirigiendo con un mensaje
        return redirect(url_for('index'))
    
    # Guardar los resultados en la sesión o pasarlos como parámetro
    return render_template('resultados.html', 
                         libros=resultados.get('items', []),
                         query=query)

@app.route('/buscar_x_categoria', methods=['POST'])
def buscar_categoria():
    """Ruta que procesa la búsqueda y redirecciona a los resultados"""
    query = request.form.get('query', '')
    if not query:
        return redirect(url_for('index'))
        
    resultados = buscar_libros_categoria(query)
    
    print(resultados)
    if resultados is None:
        # Manejar el error redirigiendo con un mensaje
        return redirect(url_for('index'))
    
    # Guardar los resultados en la sesión o pasarlos como parámetro
    return render_template('resultados.html', 
                         libros=resultados.get('items', []),
                         query=query)    


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

if __name__ == '__main__':
    app.run(debug=True)