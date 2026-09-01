# Letras Inclusivas: Traductor de Imagenes de Texto Escrito de Español a Braille

## Descripción

Letras Inclusivas es una herramienta innovadora diseñada para convertir texto escrito en español a braille. Esta aplicación busca facilitar el acceso a la información escrita a personas con discapacidad visual, promoviendo la inclusión y la igualdad. Nuestro proyecto está inspirado por la experiencia personal de un miembro del equipo, cuyo familiar tiene discapacidad visual, con la esperanza de crear una forma para que esa persona "vuelva a ver".

## Características

- **Precisión y rapidez:** Conversión eficiente y exacta de texto español a braille utilizando avanzados algoritmos de procesamiento de lenguaje natural.
- **Interfaz amigable:** Diseño intuitivo y accesible, pensado específicamente para personas con discapacidad visual.
- **Compatibilidad:** Compatible con una amplia gama de dispositivos, incluyendo smartphones, tablets y computadoras.
- **Asequibilidad:** Solución económica para ampliar su alcance y beneficiar a más personas.

## Requisitos Previos del Sistema

Para el procesamiento de documentos escaneados e imágenes a texto y Braille, se requiere tener instaladas las siguientes herramientas en tu sistema operativo:

- **Tesseract OCR:** Motor de reconocimiento óptico de caracteres (OCR).
  - *Windows:* Instalar desde el instalador oficial de Tesseract y asegurarse de agregar los datos de idioma español (`spa.traineddata`).
  - *Ubuntu/Debian:* `sudo apt-get install tesseract-ocr tesseract-ocr-spa`
  - *macOS:* `brew install tesseract tesseract-lang`
- **Poppler:** Necesario para que `pdf2image` pueda convertir páginas de PDF en imágenes.
  - *Windows:* Descargar los binarios de Poppler y agregarlos al PATH.
  - *Ubuntu/Debian:* `sudo apt-get install poppler-utils`
  - *macOS:* `brew install poppler`

## Instalación

Sigue estos pasos para instalar y ejecutar la aplicación:

1. **Clona el repositorio:**
    ```bash
    git clone https://github.com/Oiciruamz/hack2024.git
    cd hack2024
    ```

2. **Configura y activa un entorno virtual:**
    ```bash
    # En Linux / macOS:
    python -m venv venv
    source venv/bin/activate

    # En Windows (PowerShell / CMD):
    python -m venv venv
    venv\Scripts\activate
    ```

3. **Instala las dependencias necesarias:**
    ```bash
    pip install -r requirements.txt
    ```

## Uso

Para iniciar el servidor web de la aplicación (Flask):

```bash
python app.py
```

Luego, abre tu navegador web e ingresa a:
```
http://localhost:5000
```

### Funcionalidades Disponibles:
- **Traducción de PDF a Braille:** Sube un archivo PDF para extraer su texto y generar el documento Braille (descargable en formato PDF o BRF).
- **Traductor Braille a Texto:** Pega código Braille unicode para convertirlo a texto en español y estructurar tablas automáticamente.
- **Biblioteca y Búsqueda:** Explora libros recomendados o busca títulos y categorías mediante integración con Google Books.
