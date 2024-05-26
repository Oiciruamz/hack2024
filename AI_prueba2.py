import pytesseract
from PIL import Image
import streamlit as st
import main

# Implementación del header con HTML y CSS
st.markdown("""
    <style>
    .header {
        background-color: #0d47a1;
        padding: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: white;
        width: 100%;
        box-sizing: border-box;
    }
    .header-left {
        text-align: left;
    }
    .header-left h1, .header-left .braille {
        margin: 0;
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
    }
    </style>
    <div class="header">
        <div class="header-left">
            <h1>Letras inclusivas</h1>
            <div class="braille">⠠⠇⠑⠞⠁⠎ ⠊⠝⠉⠇⠥⠎⠊⠧⠁⠎</div>
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
            
        st.subheader("Texto extraído de la imagen:")   
        st.write(texto)
        
        braille = main.user_text(texto)
        st.subheader("Texto traducido a Braille:")
        st.markdown(braille)
    
    except Exception as e:
        st.write("An error occurred: {}".format(e))
        
else:
    st.write("Por favor, sube una imagen.")
