from fastapi import FastAPI
from fastapi.responses import FileResponse
from diffusers import KandinskyV22PriorPipeline, KandinskyV22Pipeline
from diffusers.utils import load_image
import torch

app = FastAPI()

# Cargar modelos al iniciar el servidor
pipe_prior = KandinskyV22PriorPipeline.from_pretrained(
    "kandinsky-community/kandinsky-2-2-prior", torch_dtype=torch.float16
).to("cuda")

pipe = KandinskyV22Pipeline.from_pretrained(
    "kandinsky-community/kandinsky-2-2-decoder", torch_dtype=torch.float16
).to("cuda")


@app.get("/generate-image")
async def generate_image():
    # Cargar imágenes remotas
    img1 = load_image(
        "https://huggingface.co/datasets/hf-internal-testing/diffusers-images/resolve/main/kandinsky/cat.png"
    )
    img2 = load_image(
        "https://huggingface.co/datasets/hf-internal-testing/diffusers-images/resolve/main/kandinsky/starry_night.jpeg"
    )

    # Condiciones y pesos
    images_texts = ["a cat", img1, img2]
    weights = [0.3, 0.3, 0.4]
    prompt = ""

    # Proceso de generación
    prior_out = pipe_prior.interpolate(images_texts, weights)
    image = pipe(**prior_out, height=768, width=768).images[0]

    # Guardar imagen como JPG
    output_path = "output.jpg"
    image.save(output_path, format="JPEG")

    return FileResponse(output_path, media_type="image/jpeg", filename="output.jpg")
