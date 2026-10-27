"""
Integración con Firebase (Admin SDK) para Letras Inclusivas.

- Verifica los ID tokens que el navegador obtiene con el Firebase JS SDK.
- Persiste usuarios y sus listas de libros en Firestore.

Modelo de datos:
    users/{uid}                    -> {email, nombre, creado_en, ultimo_acceso}
    users/{uid}/listas/{listaId}   -> {nombre, libros: [{id, titulo, autor, imagen}],
                                       creado_en, actualizado_en}

Los libros se guardan desnormalizados (snapshot de título/autor/imagen) para que
las listas sobrevivan reinicios del servidor sin volver a consultar Google Books.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    import firebase_admin
    from firebase_admin import auth, credentials, firestore
except ImportError:  # firebase-admin no instalado
    firebase_admin = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_LISTAS_POR_USUARIO = 50
MAX_LIBROS_POR_LISTA = 500

_db = None
_error_inicializacion: Optional[str] = None


class FirebaseNoConfigurado(RuntimeError):
    """Firebase no está disponible (falta la dependencia o las credenciales)."""


class ListaNoEncontrada(LookupError):
    """La lista no existe o no pertenece al usuario."""


class TokenInvalido(ValueError):
    """El ID token de Firebase es inválido o expiró."""


def _inicializar() -> None:
    """Inicializa firebase_admin una sola vez de forma perezosa."""
    global _db, _error_inicializacion
    if _db is not None or _error_inicializacion is not None:
        return

    if firebase_admin is None:
        _error_inicializacion = "Falta instalar 'firebase-admin' (pip install -r requirements.txt)."
        return

    ruta = os.getenv('FIREBASE_CREDENTIALS', 'firebase-service-account.json')
    ruta_cred = Path(ruta)
    if not ruta_cred.is_absolute():
        ruta_cred = PROJECT_ROOT / ruta_cred

    if not ruta_cred.exists():
        _error_inicializacion = (
            f"No se encontró el archivo de credenciales de Firebase en '{ruta_cred}'. "
            "Descárgalo desde Configuración del proyecto > Cuentas de servicio."
        )
        return

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(str(ruta_cred)))
        _db = firestore.client()
    except Exception as exc:  # credenciales corruptas, etc.
        _error_inicializacion = f"Error al inicializar Firebase: {exc}"


def disponible() -> bool:
    _inicializar()
    return _db is not None


def error_configuracion() -> Optional[str]:
    _inicializar()
    return _error_inicializacion


def _cliente():
    _inicializar()
    if _db is None:
        raise FirebaseNoConfigurado(_error_inicializacion or "Firebase no está configurado.")
    return _db


# --------------------------------------------------------------------------
# Autenticación
# --------------------------------------------------------------------------

def verificar_token(id_token: str) -> Dict:
    """Valida un ID token de Firebase y devuelve sus claims (uid, email, name...)."""
    _cliente()
    if not id_token or not isinstance(id_token, str):
        raise TokenInvalido("Token vacío.")
    try:
        return auth.verify_id_token(id_token, clock_skew_seconds=10)
    except Exception as exc:
        raise TokenInvalido(str(exc)) from exc


def obtener_o_crear_usuario(uid: str, email: str, nombre: str = '') -> Dict:
    """Crea/actualiza el documento users/{uid} y devuelve {uid, email, nombre}."""
    db = _cliente()
    ref = db.collection('users').document(uid)
    snap = ref.get()

    if snap.exists:
        datos = snap.to_dict() or {}
        cambios = {'ultimo_acceso': firestore.SERVER_TIMESTAMP}
        if email and datos.get('email') != email:
            cambios['email'] = email
        if nombre and not datos.get('nombre'):
            cambios['nombre'] = nombre
        ref.update(cambios)
        datos.update({k: v for k, v in cambios.items() if k != 'ultimo_acceso'})
    else:
        datos = {
            'email': email,
            'nombre': nombre or (email.split('@')[0] if email else 'Usuario'),
            'creado_en': firestore.SERVER_TIMESTAMP,
            'ultimo_acceso': firestore.SERVER_TIMESTAMP,
        }
        ref.set(datos)

    return {'uid': uid, 'email': datos.get('email', email), 'nombre': datos.get('nombre', nombre)}


def obtener_usuario(uid: str) -> Optional[Dict]:
    snap = _cliente().collection('users').document(uid).get()
    if not snap.exists:
        return None
    datos = snap.to_dict() or {}
    return {'uid': uid, 'email': datos.get('email', ''), 'nombre': datos.get('nombre', '')}


# --------------------------------------------------------------------------
# Listas
# --------------------------------------------------------------------------

def _col_listas(uid: str):
    return _cliente().collection('users').document(uid).collection('listas')


def _serializar_lista(snap) -> Dict:
    datos = snap.to_dict() or {}
    return {
        'id': snap.id,
        'nombre': datos.get('nombre', 'Sin nombre'),
        'libros': list(datos.get('libros', [])),
    }


def obtener_listas(uid: str) -> List[Dict]:
    """Listas del usuario ordenadas por fecha de creación."""
    docs = _col_listas(uid).order_by('creado_en').stream()
    return [_serializar_lista(d) for d in docs]


def obtener_lista(uid: str, lista_id: str) -> Dict:
    if not lista_id:
        raise ListaNoEncontrada(lista_id)
    snap = _col_listas(uid).document(str(lista_id)).get()
    if not snap.exists:
        raise ListaNoEncontrada(lista_id)
    return _serializar_lista(snap)


def crear_lista(uid: str, nombre: str) -> Dict:
    col = _col_listas(uid)
    total = sum(1 for _ in col.limit(MAX_LISTAS_POR_USUARIO).stream())
    if total >= MAX_LISTAS_POR_USUARIO:
        raise ValueError(f"Alcanzaste el máximo de {MAX_LISTAS_POR_USUARIO} listas.")

    ref = col.document()
    ref.set({
        'nombre': nombre[:80],
        'libros': [],
        'creado_en': firestore.SERVER_TIMESTAMP,
        'actualizado_en': firestore.SERVER_TIMESTAMP,
    })
    return {'id': ref.id, 'nombre': nombre[:80], 'libros': []}


def eliminar_lista(uid: str, lista_id: str) -> None:
    ref = _col_listas(uid).document(str(lista_id))
    if not ref.get().exists:
        raise ListaNoEncontrada(lista_id)
    ref.delete()


def agregar_libro(uid: str, lista_id: str, libro: Dict) -> List[Dict]:
    """Agrega un libro (sin duplicar) dentro de una transacción. Devuelve los libros."""
    db = _cliente()
    ref = _col_listas(uid).document(str(lista_id))
    entrada = {
        'id': str(libro['id']),
        'titulo': str(libro.get('titulo', ''))[:300],
        'autor': str(libro.get('autor', ''))[:300],
        'imagen': str(libro.get('imagen', ''))[:1000],
    }

    @firestore.transactional
    def _tx(transaction):
        snap = ref.get(transaction=transaction)
        if not snap.exists:
            raise ListaNoEncontrada(lista_id)
        libros = list((snap.to_dict() or {}).get('libros', []))
        if any(str(b.get('id')) == entrada['id'] for b in libros):
            return libros
        if len(libros) >= MAX_LIBROS_POR_LISTA:
            raise ValueError(f"La lista alcanzó el máximo de {MAX_LIBROS_POR_LISTA} libros.")
        libros.append(entrada)
        transaction.update(ref, {'libros': libros, 'actualizado_en': firestore.SERVER_TIMESTAMP})
        return libros

    return _tx(db.transaction())


def eliminar_libro(uid: str, lista_id: str, libro_id: str) -> Optional[List[Dict]]:
    """Quita un libro de la lista. Devuelve los libros restantes o None si no estaba."""
    db = _cliente()
    ref = _col_listas(uid).document(str(lista_id))
    objetivo = str(libro_id).strip()

    @firestore.transactional
    def _tx(transaction):
        snap = ref.get(transaction=transaction)
        if not snap.exists:
            raise ListaNoEncontrada(lista_id)
        libros = list((snap.to_dict() or {}).get('libros', []))
        restantes = [b for b in libros if str(b.get('id', '')).strip() != objetivo]
        if len(restantes) == len(libros):
            return None
        transaction.update(ref, {'libros': restantes, 'actualizado_en': firestore.SERVER_TIMESTAMP})
        return restantes

    return _tx(db.transaction())
