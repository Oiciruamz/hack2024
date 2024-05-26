from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image

import requests

import main

processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")

# load image from the IAM dataset
url = "https://fki.tic.heia-fr.ch/static/img/a01-122-02.jpg"

image_path = "TextToBraille.png"
image = Image.open(image_path).convert("RGB")

pixel_values = processor(image, return_tensors="pt").pixel_values
generated_ids = model.generate(pixel_values, max_new_tokens=50)

generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

print(main.user_text(generated_text))
