from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image

import requests

import main


def divide_image_horizontal(image_path):
    # Abrir la imagen original
    image = Image.open(image_path)
    
    # Calcular el punto medio horizontal
    width, height = image.size
    middle_point = height // 2
    
    # Dividir la imagen en dos partes
    top_half = image.crop((0, 0, width, middle_point))
    bottom_half = image.crop((0, middle_point, width, height))
    
    # Guardar o retornar las imágenes
    top_half.save('top_half.jpg')
    bottom_half.save('bottom_half.jpg')
    return top_half, bottom_half



processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")

# load image from the IAM dataset
url = "https://fki.tic.heia-fr.ch/static/img/a01-122-02.jpg"

image_path = "TextToBraille.png"

texto = ""

images = divide_image_horizontal(image_path)

for image in images:
    
    
    image.show()
    
    pixel_values = processor(image, return_tensors="pt").pixel_values
    generated_ids = model.generate(pixel_values, max_new_tokens=50)
    
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    texto = texto + generated_text
    

print(main.user_text(texto))