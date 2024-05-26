import pytesseract
from PIL import Image

import streamlit as st

import main



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
    st.write("Please upload an image.")
    
    try:
         
        lines = count_text_lines(image_path)
        for line in lines:
            texto+=line + " "
            
        
        st.write(main.user_text(texto))
            
    
    except Exception as e:
        st.write("An error occurred: {}".format(e))
        
else:
    st.write("Please upload an image.")
            