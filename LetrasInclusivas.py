import pytesseract
from PIL import Image
import streamlit as st
import main

from pdfDown import PDF, create_pdf

st.set_page_config(page_title="Traductor de texto a Braille", page_icon="🔠", layout="wide")

# Implementación del header con HTML y CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inria+Serif:wght@400;700&display=swap');

    .header {
        background-color: #18407B;
        padding: 20px;
        display: flex;
        justify-content: space-between;
        box-shadow: 0 4px 6px 0 black;
        align-items: center;
        width: 100%;
        box-sizing: border-box;
        font-family: 'Inria Serif', serif;
    }
    .header-left {
        text-align: left;
    }
    .header-left h1, .header-left .braille {
        margin: 0;
        font-family: 'Inria Serif', serif;
    }
    .header-left h1 {
        font-size: 2.5em;
    }
    .header-left .braille {
        margin-top: 10px;
        font-size: 1.2em;
    }
    .header-right {
        text-align: right;
        font-size: 1.5em;
        font-family: 'Inria Serif', serif;
    }
    body, h1, h2, h3, h4, h5, h6, p, div {
        font-family: 'Inria Sans', sans;
    }
    .braille-container {
        background-color: #231c1c;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px 0 rgba(0, 0, 0, 0.1);
        margin-top: 20px;
    }
    </style>
    <div class="header">
        <div class="header-left">
            <h1>Letras inclusivas</h1>
            <div class="braille">⠠⠇⠑⠗⠁⠎ ⠊⠝⠉⠇⠥⠎⠊⠧⠁⠎</div>
        </div>
        <div class="header-right">
            <h2>Cambiando el mundo un texto a la vez</h2>
        </div>
    </div>
""", unsafe_allow_html=True)

st.title("Traductor de texto a Braille")

# Función para contar líneas de texto en una imagen
def count_text_lines(image_path):
    # Abrir la imagen con PIL
    image = Image.open(image_path)

    # Configuración para usar Tesseract OCR para detectar líneas
    custom_config = r'--oem 3 --psm 4'
    # oem 3 es para usar tanto el motor heredado como LSTM, y psm 4 trata cada línea como una línea separada.

    # Extraer texto de la imagen con la configuración específica
    text = pytesseract.image_to_string(image, config=custom_config)

    # Dividir el texto por líneas y filtrar líneas vacías
    lines = [line for line in text.split('\n') if line.strip()]

    # Retornar la cantidad de líneas y opcionalmente las líneas mismas
    return lines

# Uso de la función
image_path = st.file_uploader("Sube un archivo con texto para traducirlo a Braille", type=["jpg", "jpeg", "png"])

texto = ""

if image_path is not None:
    try:
        st.image(image_path, use_column_width=True)
         
        lines = count_text_lines(image_path)
        for line in lines:
            texto += line + " "
        
        braille = main.user_text(texto)
        st.subheader("Texto traducido a Braille:")
        st.markdown(f"""
            <div class="braille-container">
                {braille}
            </div>
        """, unsafe_allow_html=True)
        def create_pdf(text, file_path):
            pdf = PDF()
            pdf.download_braille(text, file_path)
        
        
        st.button("Descargar Braille", on_click=create_pdf(braille, "mi_documento_braille.pdf"))
            
    
    except Exception as e:
        st.write("An error occurred: {}".format(e))
        
else:
    st.write("Por favor, sube una imagen.")
