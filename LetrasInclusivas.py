import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path
from app.pdfDown import PDF, create_pdf


def preprocess_image(image):
    # Convertir a escala de grises
    gray_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    return gray_image

def binarize_image(gray_image):
    # Aplicar un umbral binario para que el fondo sea blanco y el texto negro
    _, binarized_image = cv2.threshold(gray_image, 150, 255, cv2.THRESH_BINARY)
    return binarized_image

def remove_noise(image):
    # Aplicar un filtro mediano para eliminar ruido
    denoised_image = cv2.medianBlur(image, 3)
    return denoised_image

def apply_dilation(image):
    kernel = np.ones((1, 1), np.uint8)
    dilated_image = cv2.dilate(image, kernel, iterations=1)
    return dilated_image

def resize_image(image, scale=2):
    # Cambiar el tamaño de la imagen para hacerla más grande
    width = int(image.shape[1] * scale)
    height = int(image.shape[0] * scale)
    resized_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
    return resized_image

def preprocess_image_for_ocr(image):
    # Convertir a escala de grises
    gray_image = preprocess_image(image)
    # Aplicar umbral binario
    binarized_image = binarize_image(gray_image)
    # Reducir ruido
    denoised_image = remove_noise(binarized_image)
    # Aplicar dilatación
    dilated_image = apply_dilation(denoised_image)
    # Redimensionar para mejor legibilidad
    resized_image = resize_image(dilated_image)
    return resized_image

# Función para contar líneas de texto en una imagen
def count_text_lines(pdf_path):
    # Convertir PDF a imágenes
    images = convert_from_path(pdf_path)

    all_lines = []

    for image in images:
        # Preprocesar la imagen
        preprocessed_image = preprocess_image_for_ocr(image)

        # Configuración para usar Tesseract OCR para detectar líneas
        custom_config = r'--oem 3 --psm 4'
        # Extraer texto de la imagen con la configuración específica
        text = pytesseract.image_to_string(preprocessed_image, lang='spa', config=custom_config)

        # Dividir el texto por líneas y filtrar líneas vacías
        lines = [line for line in text.split('\n') if line.strip()]

        all_lines.extend(lines)

    # Retornar todas las líneas
    return all_lines
