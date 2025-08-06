from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from io import BytesIO
import base64
from PIL import Image
import torch
from diffusers import StableDiffusionPipeline

# Inicializa FastAPI
app = FastAPI()

# CORS (para frontend desde otro dominio)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelo para recibir el prompt
class PromptRequest(BaseModel):
    prompt: str

# Cargar el modelo (esto toma unos segundos)
pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
)
pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")

@app.post("/generate-image")
async def generate_image(data: PromptRequest):
    try:
        # Generar imagen
        image = pipe(data.prompt).images[0]

        # Convertir a base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return {"success": True, "image_base64": img_str}
    except Exception as e:
        return {"success": False, "error": str(e)}
