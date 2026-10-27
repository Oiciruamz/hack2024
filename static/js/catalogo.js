// ==========================================================================
// Catálogo: lógica de "Guardar en lista" + colores de tarjetas.
// Compartido por inicio.html y resultados.html (ver partials/modal_guardar.html).
// ==========================================================================

// Referencias a los elementos
const modal = document.getElementById('modal');
const modal_contenido = document.getElementById('modal-content');
const titulo = document.getElementById('modal-title');
const closeBtn = document.getElementById('close-btn');
const agregarBtn = document.getElementById('agregar-btn');
const crearListaBtn = document.getElementById('crear-lista-btn');
const nuevaListaContenido = document.getElementById('nueva-lista-contenido');
const listaContenido = document.getElementById('lista-contenido');
const cancelarNuevaListaBtn = document.getElementById('cancelar-nueva-lista');
const nuevaListaConfirmBtn = document.getElementById('nueva-lista-confirm');
const inputText = document.getElementById('input-text');

// Libro seleccionado: { id, titulo, autor, imagen }. Los datos extra permiten
// al backend registrar libros de Google Books (IDs 'gb_...').
let libroSeleccionado = null;

// Si la sesión expiró, el backend responde 401: mandar al login y volver aquí.
function redirigirSiNoAutenticado(response) {
    if (response.status === 401) {
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.assign('/login?next=' + next);
        return true;
    }
    return false;
}

async function obtenerListas() {
    try {
        const response = await fetch('/listas', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (redirigirSiNoAutenticado(response)) return [];
        if (!response.ok) {
            throw new Error('Error en la red');
        }

        const data = await response.json();
        return data.listas || [];
    } catch (error) {
        console.error('Hubo un problema con la petición Fetch:', error);
        return [];
    }
}

async function agregarLibroALista(libro, listaId) {
    try {
        const response = await fetch('/agregar_libro', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                libro_id: libro.id,
                lista_id: listaId,
                titulo: libro.titulo,
                autor: libro.autor,
                imagen: libro.imagen
            })
        });

        if (redirigirSiNoAutenticado(response)) return;
        const result = await response.json();

        if (response.ok) {
            alert(result.message);
            window.location.reload();
        } else {
            alert('Error al agregar el libro: ' + result.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Ocurrió un error al intentar agregar el libro.');
    }
}

async function crearNuevaLista(nombre) {
    const response = await fetch('/crear_lista', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ nombre: nombre })
    });
    if (redirigirSiNoAutenticado(response)) return { success: false, message: 'Debes iniciar sesión.' };
    return await response.json();
}

function showNuevaListaForm() {
    modal_contenido.style.width = "500px";
    titulo.textContent = "Nueva lista";
    listaContenido.style.display = "none";
    nuevaListaContenido.style.display = "block";
    inputText.value = "";
}

function showExistingListas() {
    modal_contenido.style.width = "300px";
    titulo.textContent = "Añadir a lista";
    listaContenido.style.display = "block";
    nuevaListaContenido.style.display = "none";
}

async function handleGuardarClick() {
    libroSeleccionado = {
        id: this.getAttribute('data-libro-id'),
        titulo: this.getAttribute('data-titulo') || '',
        autor: this.getAttribute('data-autor') || '',
        imagen: this.getAttribute('data-imagen') || ''
    };
    modal.style.display = "flex";

    try {
        const listas = await obtenerListas();
        if (!listas || listas.length === 0) {
            showNuevaListaForm();
        } else {
            showExistingListas();
        }
    } catch (error) {
        console.error("Error al verificar las listas:", error);
    }
}

function setupGuardarButtons() {
    document.querySelectorAll('.guardar-btn').forEach(button => {
        button.addEventListener('click', handleGuardarClick);
    });
}

if (agregarBtn) {
    agregarBtn.addEventListener('click', async function () {
        const listaSeleccionada = document.querySelector('input[name="lista"]:checked');

        if (listaSeleccionada && libroSeleccionado) {
            const listaId = listaSeleccionada.value;
            await agregarLibroALista(libroSeleccionado, listaId);
        } else if (!listaSeleccionada) {
            alert('Por favor, selecciona una lista antes de agregar el libro.');
        }
    });
}

if (nuevaListaConfirmBtn) {
    nuevaListaConfirmBtn.addEventListener('click', async function () {
        const nombre_lista = inputText.value.trim();
        if (nombre_lista && libroSeleccionado) {
            try {
                const result = await crearNuevaLista(nombre_lista);
                if (result.success) {
                    modal.style.display = "none";
                    alert(result.message);
                    await agregarLibroALista(libroSeleccionado, result.lista_id);
                } else {
                    alert('Error al crear la lista: ' + result.message);
                }
            } catch (error) {
                console.error('Error al crear la lista:', error);
                alert('Error al crear la lista. Por favor, intente de nuevo.');
            }
        } else if (!nombre_lista) {
            alert('Por favor, ingrese un nombre para la lista.');
        }
    });
}

// Aplicar colores de fondo dinámicos a las tarjetas
document.querySelectorAll('.color-tarjeta[data-color]').forEach(el => {
    const color = el.getAttribute('data-color');
    if (color) el.style.backgroundColor = color;
});

// Inicializar la configuración de los botones
setupGuardarButtons();

// Cerrar modal cuando se haga clic en el botón de cerrar (X)
if (closeBtn) {
    closeBtn.onclick = function () {
        modal.style.display = "none";
    };
}

// Cerrar modal cuando se haga clic fuera del contenido del modal
window.onclick = function (event) {
    if (event.target === modal) {
        modal.style.display = "none";
    }
};

// Cambiar a la opción de crear nueva lista
if (crearListaBtn) {
    crearListaBtn.onclick = function () {
        showNuevaListaForm();
    };
}

// Volver al contenido de selección de lista
if (cancelarNuevaListaBtn) {
    cancelarNuevaListaBtn.onclick = function () {
        showExistingListas();
    };
}
