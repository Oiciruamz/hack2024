import importlib.util
import os
import sys
from pathlib import Path
import random
import uuid
import requests
from typing import Dict, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
load_dotenv(PROJECT_ROOT / ".env")
PACKAGE_DIR = PROJECT_ROOT / "app"

spec_pkg = importlib.util.spec_from_file_location("app", PACKAGE_DIR / "__init__.py")
app_pkg = importlib.util.module_from_spec(spec_pkg)
app_pkg.__path__ = [str(PACKAGE_DIR)]
sys.modules["app"] = app_pkg
spec_pkg.loader.exec_module(app_pkg)

spec_main = importlib.util.spec_from_file_location("app.main", PACKAGE_DIR / "main.py")
mn = importlib.util.module_from_spec(spec_main)
sys.modules["app.main"] = mn
spec_main.loader.exec_module(mn)

spec_pdfdown = importlib.util.spec_from_file_location("app.pdfDown", PACKAGE_DIR / "pdfDown.py")
pdfDown_mod = importlib.util.module_from_spec(spec_pdfdown)
sys.modules["app.pdfDown"] = pdfDown_mod
spec_pdfdown.loader.exec_module(pdfDown_mod)
PDF = pdfDown_mod.PDF

spec_ocr = importlib.util.spec_from_file_location("app.ocr_mistral", PACKAGE_DIR / "ocr_mistral.py")
ocr_mistral = importlib.util.module_from_spec(spec_ocr)
sys.modules["app.ocr_mistral"] = ocr_mistral
spec_ocr.loader.exec_module(ocr_mistral)

spec_fb = importlib.util.spec_from_file_location("app.firebase_service", PACKAGE_DIR / "firebase_service.py")
fb = importlib.util.module_from_spec(spec_fb)
sys.modules["app.firebase_service"] = fb
spec_fb.loader.exec_module(fb)

TEMP_FILES_DIR = str(PROJECT_ROOT / "temp_files")
os.makedirs(TEMP_FILES_DIR, exist_ok=True)

from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, session, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_BOOKS_KEY = os.getenv('GOOGLE_BOOKS_API_KEY', 'AIzaSyAAUx82Bb6dJvUpJ2dZnWSNsejemaXhOY8')
GOOGLE_BOOKS_PAGINA = 40      # Máximo permitido por la API por petición
GOOGLE_BOOKS_MAX_PAGINAS = 3  # Tope de peticiones por búsqueda

# Géneros del dropdown "Catálogo". La clave es lo que envía el formulario y
# 'q' la consulta real a Google Books. Patrón validado contra la API:
# 'subject:<tema en inglés> <término en español>' ('categories:' no existe y
# 'subject:' en español devuelve 0 resultados). Agregar un género = 1 línea.
GENEROS_CATALOGO = {
    'terror':   {'nombre': 'Terror',                 'q': 'subject:fiction terror'},
    'clasicos': {'nombre': 'Clásicos',               'q': 'subject:fiction clásicos'},
    'ciencias': {'nombre': 'Ciencias y matemáticas', 'q': 'subject:mathematics matemáticas'},
}

# Registro en memoria de libros de Google Books mostrados/guardados,
# indexado por ID con prefijo 'gb_' para no chocar con el catálogo local.
libros_externos: Dict[str, Dict] = {}


def _a_https(url: str) -> str:
    """Evita contenido mixto: Google a veces devuelve portadas con http://."""
    if url and url.startswith('http://'):
        return 'https://' + url[len('http://'):]
    return url


def _consultar_google_books(q: str, lang: Optional[str] = None, objetivo: int = 20) -> list:
    """
    Consulta Google Books paginando con startIndex hasta reunir `objetivo`
    libros que tengan portada, título y autores (sin duplicados).

    Lanza requests.RequestException si falla la primera página; si falla una
    página posterior, devuelve lo reunido hasta ese momento.
    """
    vistos = set()
    resultados = []

    for pagina in range(GOOGLE_BOOKS_MAX_PAGINAS):
        params = {
            'q': q,
            'key': GOOGLE_BOOKS_KEY,
            'maxResults': GOOGLE_BOOKS_PAGINA,
            'startIndex': pagina * GOOGLE_BOOKS_PAGINA,
            'orderBy': 'relevance',
            'printType': 'books',
            'fields': 'items(id,volumeInfo(title,authors,description,imageLinks,categories,publishedDate))',
        }
        if lang:
            params['langRestrict'] = lang

        try:
            response = requests.get(GOOGLE_BOOKS_URL, params=params, timeout=10)
            response.raise_for_status()
            items = response.json().get('items', [])
        except requests.exceptions.RequestException:
            if pagina == 0:
                raise
            break

        if not items:
            break

        for libro in items:
            volume_id = libro.get('id')
            volumeInfo = libro.get('volumeInfo', {})
            thumbnail = volumeInfo.get('imageLinks', {}).get('thumbnail')
            if not (volume_id and thumbnail and volumeInfo.get('title') and volumeInfo.get('authors')):
                continue
            if volume_id in vistos:
                continue
            vistos.add(volume_id)

            resultados.append({
                'id': volume_id,
                'volumeInfo': {
                    'title': volumeInfo['title'],
                    'authors': volumeInfo['authors'],
                    'description': volumeInfo.get('description', 'Descripción no disponible'),
                    'imageLinks': {'thumbnail': _a_https(thumbnail)},
                    'categories': volumeInfo.get('categories', []),
                    'publishedDate': volumeInfo.get('publishedDate', ''),
                }
            })
            if len(resultados) >= objetivo:
                return resultados

        if len(items) < GOOGLE_BOOKS_PAGINA:
            break  # No hay más páginas

    return resultados


def buscar_libros(query: str, max_results: int = 20) -> Optional[Dict]:
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

        libros_con_imagenes = _consultar_google_books(query, objetivo=max_results)

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


def buscar_libros_categoria(categoria, max_results: int = 20) -> Optional[Dict]:
    """
    Busca libros de un género del catálogo. `categoria` puede ser una clave de
    GENEROS_CATALOGO (p. ej. 'terror') o texto libre como respaldo.
    """
    try:
        if not categoria:
            raise ValueError("Query es obligatorio")

        clave = str(categoria).strip().lower()
        genero = GENEROS_CATALOGO.get(clave)
        consulta = genero['q'] if genero else str(categoria).strip()

        libros_con_imagenes = _consultar_google_books(consulta, lang='es', objetivo=max_results)

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


def normalizar_libro_google(item: Dict) -> Dict:
    """
    Convierte un resultado de Google Books al mismo formato que el catálogo
    local ({id, titulo, autor, imagen, color}) y lo registra en libros_externos.
    """
    volumeInfo = item.get('volumeInfo', {})
    libro = {
        'id': f"gb_{item['id']}",
        'titulo': volumeInfo.get('title', 'Sin título'),
        'autor': ', '.join(volumeInfo.get('authors', [])),
        'imagen': volumeInfo.get('imageLinks', {}).get('thumbnail', ''),
    }
    libros_externos[libro['id']] = dict(libro)
    libro['color'] = generar_color_pastel()
    return libro


def obtener_libro(libro_id) -> Optional[Dict]:
    """Resuelve un ID guardado en una lista: local (entero) o Google ('gb_...')."""
    sid = str(libro_id).strip()
    if sid.startswith('gb_'):
        return libros_externos.get(sid)
    try:
        lid = int(sid)
    except (ValueError, TypeError):
        return None
    return next((libro for libro in libros if libro['id'] == lid), None)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or 'dev-inseguro-define-SECRET_KEY-en-.env'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None

# Configuración pública del Firebase JS SDK (no es secreta, identifica el proyecto).
FIREBASE_WEB_CONFIG = {
    'apiKey': os.getenv('FIREBASE_API_KEY', ''),
    'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN', ''),
    'projectId': os.getenv('FIREBASE_PROJECT_ID', ''),
    'appId': os.getenv('FIREBASE_APP_ID', ''),
}
FIREBASE_WEB_LISTO = all(FIREBASE_WEB_CONFIG.values())


@app.context_processor
def inyectar_generos_catalogo():
    """Disponibiliza los géneros del dropdown "Catálogo" en todas las plantillas."""
    return {'generos_catalogo': GENEROS_CATALOGO}


@app.context_processor
def inyectar_firebase():
    return {'firebase_config': FIREBASE_WEB_CONFIG, 'firebase_web_listo': FIREBASE_WEB_LISTO}


class User(UserMixin):
    """Usuario autenticado con Firebase. `id` es el UID de Firebase."""
    def __init__(self, uid, email, nombre=''):
        self.id = uid
        self.email = email
        self.nombre = nombre or (email.split('@')[0] if email else 'Usuario')


def _es_peticion_api() -> bool:
    """True si la petición es un fetch/JSON (para responder 401/503 en JSON)."""
    return request.is_json or request.accept_mimetypes.best == 'application/json' \
        or request.path in ('/listas', '/crear_lista', '/agregar_libro', '/eliminar_libro', '/eliminar_lista', '/sesion')


@login_manager.unauthorized_handler
def no_autorizado():
    if _es_peticion_api():
        return jsonify({'success': False, 'message': 'Debes iniciar sesión.', 'login_url': url_for('login')}), 401
    return redirect(url_for('login', next=request.full_path.rstrip('?')))


@app.errorhandler(fb.FirebaseNoConfigurado)
def firebase_no_configurado(exc):
    mensaje = 'El servicio de cuentas no está configurado todavía.'
    app.logger.warning("[Firebase] %s", exc)
    if _es_peticion_api():
        return jsonify({'success': False, 'message': mensaje}), 503
    return mensaje, 503


def _url_siguiente_segura(destino: Optional[str]) -> str:
    """Evita open redirects: solo rutas relativas internas."""
    if destino and destino.startswith('/') and not destino.startswith('//') and '\\' not in destino:
        return destino
    return url_for('inicio')


libros = [
    {"id": 1, "imagen": "rebelion.webp", "titulo": "Rebelión en la granja", "autor": "George Orwell"},
    {"id": 2, "imagen": "1984.webp", "titulo": "1984", "autor": "George Orwell"},
    {"id": 3, "imagen": "guerra_mundos.jpg", "titulo": "La guerra de los mundos", "autor": "H.G Wells"},
    {"id": 4, "imagen": "carretera.jpg", "titulo": "La carretera", "autor": "Cormac McCarthy"},
    {"id": 5, "imagen": "metamorfosis.jpg", "titulo": "La metamorfosis", "autor": "Franz Kafka"},
    {"id": 6, "imagen": "Frankie.jpg", "titulo": "Frankenstein", "autor": "Mary Shelley"},
    {"id": 7, "imagen": "principito.jpg", "titulo": "El principito", "autor": "Antoine de Saint-Exupéry"},
    {"id": 8, "imagen": "fahrenheit451.jpg", "titulo": "Fahrenheit 451", "autor": "Ray Bradbury"},
    {"id": 9, "imagen": "mundo_feliz.jpg", "titulo": "Un mundo feliz", "autor": "Aldous Huxley"},
    {"id": 10, "imagen": "cien_anos_soledad.jpg", "titulo": "Cien años de soledad", "autor": "Gabriel García Márquez"},
    {"id": 11, "imagen": "quijote.jpg", "titulo": "Don Quijote de la Mancha", "autor": "Miguel de Cervantes"},
    {"id": 12, "imagen": "dracula.jpg", "titulo": "Drácula", "autor": "Bram Stoker"},
    {"id": 13, "imagen": "dorian_gray.jpg", "titulo": "El retrato de Dorian Gray", "autor": "Oscar Wilde"},
    {"id": 14, "imagen": "crimen_castigo.jpg", "titulo": "Crimen y castigo", "autor": "Fiódor Dostoyevski"},
    {"id": 15, "imagen": "cronica_muerte.jpg", "titulo": "Crónica de una muerte anunciada", "autor": "Gabriel García Márquez"},
    {"id": 16, "imagen": "pedro_paramo.jpg", "titulo": "Pedro Páramo", "autor": "Juan Rulfo"},
    {"id": 17, "imagen": "ensayo_ceguera.jpg", "titulo": "Ensayo sobre la ceguera", "autor": "José Saramago"},
    {"id": 18, "imagen": "el_tunel.jpg", "titulo": "El túnel", "autor": "Ernesto Sabato"},
    {"id": 19, "imagen": "ficciones.jpg", "titulo": "Ficciones", "autor": "Jorge Luis Borges"},
    {"id": 20, "imagen": "el_aleph.jpg", "titulo": "El Aleph", "autor": "Jorge Luis Borges"},
    {"id": 21, "imagen": "rayuela.jpg", "titulo": "Rayuela", "autor": "Julio Cortázar"},
    {"id": 22, "imagen": "ciudad_perros.jpg", "titulo": "La ciudad y los perros", "autor": "Mario Vargas Llosa"},
    {"id": 23, "imagen": "sombra_viento.jpg", "titulo": "La sombra del viento", "autor": "Carlos Ruiz Zafón"},
    {"id": 24, "imagen": "miserables.jpg", "titulo": "Los miserables", "autor": "Víctor Hugo"},
    {"id": 25, "imagen": "conde_montecristo.jpg", "titulo": "El conde de Montecristo", "autor": "Alejandro Dumas"}
]

@login_manager.user_loader
def load_user(user_id):
    # Usa los datos cacheados en la sesión para no consultar Firestore en cada request
    datos = session.get('usuario')
    if datos and datos.get('uid') == user_id:
        return User(datos['uid'], datos.get('email', ''), datos.get('nombre', ''))
    # Respaldo (p. ej. cookie "remember me" tras expirar la sesión)
    try:
        datos = fb.obtener_usuario(user_id)
    except fb.FirebaseNoConfigurado:
        return None
    if not datos:
        return None
    session['usuario'] = datos
    return User(datos['uid'], datos.get('email', ''), datos.get('nombre', ''))


def _error_config_visible() -> Optional[str]:
    """Detalle de configuración de Firebase: completo en debug, genérico en producción."""
    error = fb.error_configuracion()
    if not error:
        return None
    return error if app.debug else 'El servicio de cuentas no está disponible en este momento.'


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(_url_siguiente_segura(request.args.get('next')))
    return render_template('login.html', siguiente=_url_siguiente_segura(request.args.get('next')),
                           error_config=_error_config_visible())


@app.route('/registro')
def registro():
    if current_user.is_authenticated:
        return redirect(url_for('inicio'))
    return render_template('registro.html', siguiente=_url_siguiente_segura(request.args.get('next')),
                           error_config=_error_config_visible())


@app.route('/sesion', methods=['POST'])
def crear_sesion():
    """Intercambia un ID token de Firebase por una sesión de Flask."""
    data = request.get_json(silent=True) or {}
    try:
        claims = fb.verificar_token(data.get('idToken'))
    except fb.TokenInvalido:
        # SEG-001: mismo mensaje genérico para cualquier fallo de autenticación
        return jsonify({'success': False, 'message': 'Error login'}), 401

    nombre = str(data.get('nombre') or claims.get('name') or '').strip()[:60]
    usuario = fb.obtener_o_crear_usuario(claims['uid'], claims.get('email', ''), nombre)

    session.clear()
    session['usuario'] = usuario
    login_user(User(usuario['uid'], usuario['email'], usuario['nombre']), remember=True)
    return jsonify({'success': True, 'redirect': _url_siguiente_segura(data.get('next'))}), 200


@app.route('/logout')
def logout():
    session.clear()
    logout_user()
    resp = make_response(redirect(url_for('inicio')))
    cookie_name = app.config.get('REMEMBER_COOKIE_NAME', 'remember_token')
    domain = app.config.get('REMEMBER_COOKIE_DOMAIN')
    path = app.config.get('REMEMBER_COOKIE_PATH', '/')
    resp.delete_cookie(cookie_name, domain=domain, path=path)
    return resp


def _listas_usuario() -> list:
    """Listas del usuario actual o [] si no hay sesión / Firebase no responde."""
    if not current_user.is_authenticated:
        return []
    try:
        return fb.obtener_listas(current_user.id)
    except Exception as exc:
        app.logger.warning("[Firebase] No se pudieron obtener las listas: %s", exc)
        return []


def _resolver_libro(libro_id: str, data: Dict) -> Optional[Dict]:
    """Obtiene {id, titulo, autor, imagen} de un libro local o de Google Books."""
    libro = obtener_libro(libro_id)
    if libro:
        return {k: libro.get(k, '') for k in ('id', 'titulo', 'autor', 'imagen')}
    if libro_id.startswith('gb_'):
        # Si el servidor se reinició tras mostrar los resultados, usar los datos del cliente
        titulo = str(data.get('titulo') or '').strip()
        imagen = str(data.get('imagen') or '').strip()
        if titulo and imagen.startswith('http'):
            return {'id': libro_id, 'titulo': titulo,
                    'autor': str(data.get('autor') or '').strip(), 'imagen': _a_https(imagen)}
    return None

@app.route('/crear_lista', methods=['POST'])
@login_required
def crear_lista():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Error validación', 'error': 'Error validación'}), 400

    nombre_lista = data.get('nombre')
    # SEG-002: Rechazar cadenas vacías, solo espacios o NULL
    if (
        nombre_lista is None
        or not str(nombre_lista).strip()
        or str(nombre_lista).strip().upper() == 'NULL'
    ):
        return jsonify({'success': False, 'message': 'Error validación', 'error': 'Error validación'}), 400

    nombre_lista = str(nombre_lista).strip()
    try:
        lista = fb.crear_lista(current_user.id, nombre_lista)
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

    return jsonify({'success': True, 'message': 'Lista creada correctamente.', 'lista_id': lista['id']}), 201

@app.route('/agregar_libro', methods=['POST'])
@login_required
def agregar_libro():
    data = request.get_json(silent=True) or {}
    libro_id = data.get('libro_id')
    lista_id = data.get('lista_id')

    if not libro_id or not lista_id:
        return jsonify({'success': False, 'message': 'El libro ID y la lista ID son requeridos.'}), 400

    libro = _resolver_libro(str(libro_id).strip(), data)
    if not libro:
        return jsonify({'success': False, 'message': 'No se encontró la información del libro.'}), 404

    try:
        libros_lista = fb.agregar_libro(current_user.id, str(lista_id), libro)
    except fb.ListaNoEncontrada:
        return jsonify({'success': False, 'message': 'La lista no existe.'}), 404
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

    return jsonify({'success': True, 'message': 'Libro agregado correctamente.', 'libros': libros_lista}), 201

@app.route('/eliminar_libro', methods=['POST'])
@login_required
def eliminar_libro():
    data = request.get_json(silent=True) or request.form or {}
    libro_id = data.get('libro_id')
    lista_id = data.get('lista_id')

    if libro_id is None or lista_id is None:
        return jsonify({'success': False, 'message': 'El libro ID y la lista ID son requeridos.'}), 400

    try:
        restantes = fb.eliminar_libro(current_user.id, str(lista_id), str(libro_id))
    except fb.ListaNoEncontrada:
        return jsonify({'success': False, 'message': 'La lista no existe.'}), 404

    if restantes is None:
        return jsonify({'success': False, 'message': 'El libro no se encuentra en la lista.'}), 404

    return jsonify({
        'success': True,
        'message': 'Libro eliminado de la lista correctamente.',
        'libros': restantes,
        'total_libros': len(restantes)
    }), 200

@app.route('/eliminar_lista', methods=['POST'])
@login_required
def eliminar_lista():
    data = request.get_json(silent=True) or request.form or {}
    lista_id = data.get('lista_id')
    if not lista_id:
        return jsonify({'success': False, 'message': 'La lista ID es requerida.'}), 400
    try:
        fb.eliminar_lista(current_user.id, str(lista_id))
    except fb.ListaNoEncontrada:
        return jsonify({'success': False, 'message': 'La lista no existe.'}), 404
    return jsonify({'success': True, 'message': 'Lista eliminada correctamente.'}), 200

@app.route('/listas', methods=['GET'])
@login_required
def obtener_listas():
    return jsonify({'success': True, 'listas': fb.obtener_listas(current_user.id)}), 200

@app.route('/perfil')
@login_required
def perfil():
    listas_con_libros = [
        {**lista, 'color': generar_color_pastel()}
        for lista in fb.obtener_listas(current_user.id)
    ]
    return render_template('perfil.html', listas=listas_con_libros)

@app.route('/lista/<lista_id>')
@login_required
def lista_individual(lista_id):
    try:
        lista_seleccionada = fb.obtener_lista(current_user.id, lista_id)
    except fb.ListaNoEncontrada:
        return "Lista no encontrada", 404

    return render_template('lista.html', lista=lista_seleccionada, libros=lista_seleccionada['libros'])


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
    
    return render_template('inicio.html', libros=libros, listas=_listas_usuario())

# Ruta para procesar el PDF y traducirlo a Braille
@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdf_file' not in request.files:
        return 'No PDF file part', 400
    
    pdf_file = request.files['pdf_file']
    if not pdf_file or not pdf_file.filename:
        return 'No se seleccionó ningún archivo', 400

    filename = pdf_file.filename.lower().strip()

    # SEG-003: Rechazar formatos no permitidos (solo se acepta .pdf)
    if not filename.endswith('.pdf'):
        return 'Formato no permitido. Solo se aceptan archivos PDF. Rechazado', 400

    # Criterio de aceptación: Verificar que no sea un archivo corrupto
    header = pdf_file.read(5)
    pdf_file.seek(0)
    if not header.startswith(b'%PDF'):
        return 'Archivo corrupto o formato no válido', 400
    
    # Obtener el nombre original sin la extensión
    original_filename = os.path.splitext(pdf_file.filename)[0]

    # Crear directorio temporal si no existe
    if not os.path.exists(TEMP_FILES_DIR):
        os.makedirs(TEMP_FILES_DIR)

    # Guardar temporalmente el PDF
    file_path = os.path.join(TEMP_FILES_DIR, 'temp_pdf.pdf')
    pdf_file.save(file_path)

    # Extraer texto con Mistral OCR y traducir a Braille
    try:
        lines = ocr_mistral.extract_text_from_pdf(file_path)
    except ocr_mistral.MistralOCRError as exc:
        return str(exc), 502
    except Exception as exc:
        return f"Error inesperado al procesar el PDF: {exc}", 500

    texto = "\n".join(lines)
    texto = ocr_mistral.clean_and_refine_for_braille(texto, use_ai=True)
    braille = mn.user_text(texto)

    # Guardar el texto Braille temporalmente para descargarlo luego
    download_id = uuid.uuid4().hex
    braille_path = os.path.join(TEMP_FILES_DIR, f'{download_id}.txt')
    with open(braille_path, 'w', encoding='utf-8') as f:
        f.write(braille)

    # Renderizar el resultado en la página
    return render_template('traducir-completado.html', download_id=download_id, original_filename=original_filename)

def _render_resultados(resultados: Optional[Dict], titulo: str, query: str):
    """Renderiza resultados.html con libros normalizados al formato de inicio."""
    items = (resultados or {}).get('items', [])
    libros_resultado = [normalizar_libro_google(item) for item in items]
    return render_template('resultados.html',
                           libros=libros_resultado,
                           titulo=titulo,
                           query=query,
                           listas=_listas_usuario())

@app.route('/buscar', methods=['POST'])
def buscar():
    """Ruta que procesa la búsqueda y muestra los resultados"""
    query = request.form.get('query', '').strip()
    if not query:
        return redirect(url_for('inicio'))

    resultados = buscar_libros(query)
    return _render_resultados(resultados, f'Resultados de "{query}"', query)

@app.route('/buscar_x_categoria', methods=['POST'])
def buscar_categoria():
    """Ruta que procesa la búsqueda por género del catálogo y muestra los resultados"""
    query = request.form.get('query', '').strip()
    if not query:
        return redirect(url_for('inicio'))

    resultados = buscar_libros_categoria(query)
    genero = GENEROS_CATALOGO.get(query.lower())
    nombre = genero['nombre'] if genero else query
    return _render_resultados(resultados, f'Catálogo: {nombre}', nombre)


@app.route('/download_braille', methods=['POST'])
def download_braille():
    download_id = request.form.get('download_id')
    original_filename = request.form.get('original_filename', 'braille_document')
    
    if not download_id:
        return 'Descarga inválida', 400

    braille_file = os.path.join(TEMP_FILES_DIR, f'{download_id}.txt')
    # Respaldo si el archivo se creó en la ruta temporal antigua del home
    if not os.path.exists(braille_file):
        home_temp = os.path.join(os.path.expanduser('~'), 'temp_files', f'{download_id}.txt')
        if os.path.exists(home_temp):
            braille_file = home_temp

    if not os.path.exists(braille_file):
        return 'Archivo Braille no encontrado', 404

    with open(braille_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    os.makedirs(TEMP_FILES_DIR, exist_ok=True)
    file_path = os.path.join(TEMP_FILES_DIR, f'{download_id}.pdf')

    # Crear el PDF
    pdf = PDF()
    pdf.download_braille(text, file_path)

    # Verificación de seguridad por si se guardó en ~/temp_files
    if not os.path.exists(file_path):
        home_pdf = os.path.join(os.path.expanduser('~'), 'temp_files', f'{download_id}.pdf')
        if os.path.exists(home_pdf):
            file_path = home_pdf

    # Enviar el archivo para descargar con el nombre original modificado
    return send_file(file_path, as_attachment=True, download_name=f'{original_filename}_braille.pdf')

@app.route('/download_brf', methods=['POST'])
def download_brf():
    download_id = request.form.get('download_id')
    original_filename = request.form.get('original_filename', 'braille_document')
    
    if not download_id:
        return 'Descarga inválida', 400

    braille_file = os.path.join(TEMP_FILES_DIR, f'{download_id}.txt')
    if not os.path.exists(braille_file):
        home_temp = os.path.join(os.path.expanduser('~'), 'temp_files', f'{download_id}.txt')
        if os.path.exists(home_temp):
            braille_file = home_temp

    if not os.path.exists(braille_file):
        return 'Archivo Braille no encontrado', 404

    # Enviar directamente el archivo de texto pero con extensión .brf
    return send_file(braille_file, as_attachment=True, download_name=f'{original_filename}.brf')

import re

def sanitizar_nombre_archivo(nombre: str) -> str:
    """Limpia un string para que sea un nombre de archivo seguro."""
    if not nombre:
        return "libro"
    # Eliminar caracteres ilegales en Windows/Linux: \ / : * ? " < > |
    nombre_limpio = re.sub(r'[\\/*?:"<>|]', '', str(nombre))
    # Reemplazar múltiples espacios o saltos de línea por un solo espacio
    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()
    return nombre_limpio if nombre_limpio else "libro"

@app.route('/descargar_libro', methods=['GET', 'POST'])
def descargar_libro():
    titulo = request.values.get('titulo', '').strip()
    if not titulo:
        titulo = 'libro_predeterminado'
    
    nombre_archivo = sanitizar_nombre_archivo(titulo)
    if not nombre_archivo.lower().endswith('.pdf'):
        nombre_descarga = f"{nombre_archivo}.pdf"
    else:
        nombre_descarga = nombre_archivo

    predeterminado_path = PROJECT_ROOT / "resources" / "Predeterminado.pdf"
    if not predeterminado_path.exists():
        return "Archivo predeterminado no encontrado", 404
        
    return send_file(str(predeterminado_path), as_attachment=True, download_name=nombre_descarga)

def parse_braille_tables(text):
    tables = []
    
    # Buscar bloques entre [Inicio De Tabla ...] y [Fin De Tabla], tolerando mayúsculas/minúsculas y saltos de línea
    pattern = r'\[\s*INICIO\s+DE\s+TABLA(?:\s*:\s*\d+\s+columnas)?\s*\](.*?)\[\s*FIN\s+DE\s+TABLA\s*\]'
    
    for table_match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
        table_text = table_match.group(1).strip()
        
        # 1. Detectar el formato nuevo estructurado: "Fila X:" seguido de "- Encabezado: Valor"
        row_split_pattern = r'(?:^|\s)Fila\s+(\d+)\s*:'
        row_matches = list(re.finditer(row_split_pattern, table_text, flags=re.IGNORECASE))
        
        if row_matches:
            headers = []
            parsed_rows = []
            
            for i, r_match in enumerate(row_matches):
                start_row = r_match.end()
                end_row = row_matches[i+1].start() if i + 1 < len(row_matches) else len(table_text)
                row_content = table_text[start_row:end_row].strip()
                
                # Extraer pares "- Encabezado: Valor" tolerando guiones internos en valores como "1.5 - 2 min"
                item_pattern = r'-\s*([^-:\n]+?)\s*:\s*(.*?)(?=(?:\s+-\s+[^-:\n]+?\s*:|$))'
                row_dict = {}
                for item_match in re.finditer(item_pattern, row_content, flags=re.DOTALL):
                    h_name = " ".join(item_match.group(1).split())
                    val = " ".join(item_match.group(2).split())
                    if val.lower() in ("(vacio)", "(vacío)"):
                        val = ""
                    if h_name not in headers:
                        headers.append(h_name)
                    row_dict[h_name] = val
                parsed_rows.append(row_dict)
            
            if headers:
                matrix = [headers]
                for row_dict in parsed_rows:
                    row_data = [row_dict.get(h, '') for h in headers]
                    matrix.append(row_data)
                tables.append(matrix)
                continue

        # 2. Formato heredado: "Fila X, Columna Y: ..."
        cell_pattern = r'Fila\s+(\d+)\s*,\s*Columna\s+(\d+)\s*:'
        matches = list(re.finditer(cell_pattern, table_text, flags=re.IGNORECASE))
        
        if matches:
            current_table = {}
            for i, match in enumerate(matches):
                r = int(match.group(1))
                c = int(match.group(2))
                
                start_val = match.end()
                if i + 1 < len(matches):
                    end_val = matches[i+1].start()
                else:
                    end_val = len(table_text)
                    
                val = table_text[start_val:end_val]
                val = " ".join(val.split())
                current_table[(r, c)] = val
                
            max_row = max((k[0] for k in current_table.keys()), default=0)
            max_col = max((k[1] for k in current_table.keys()), default=0)
            
            if max_row > 0 and max_col > 0:
                matrix = []
                for r_idx in range(1, max_row + 1):
                    row_data = []
                    for c_idx in range(1, max_col + 1):
                        row_data.append(current_table.get((r_idx, c_idx), ''))
                    matrix.append(row_data)
                tables.append(matrix)
            continue

        # 3. Caso especial: tabla degenerada de una sola fila de encabezados ("- Columna X: ...")
        col_items = list(re.finditer(r'-\s*(?:Columna\s+\d+|[^:\n\r]+?)\s*:\s*([^\n\r]+)', table_text))
        if col_items:
            matrix = [[m.group(1).strip() for m in col_items]]
            tables.append(matrix)
            
    return tables

@app.route('/braille-a-texto', methods=['GET', 'POST'])
def braille_a_texto():
    if request.method == 'POST':
        braille_text = request.form.get('braille_text', '')
        # Traducir el texto usando main.user_braille
        translated_text = mn.user_braille(braille_text)
        
        # Extraer posibles tablas
        tables = parse_braille_tables(translated_text)
        
        return render_template('braille-resultado.html', translated_text=translated_text, tables=tables)
        
    return render_template('braille-a-texto.html')

if __name__ == '__main__':
    app.run(debug=True)