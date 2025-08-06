from fastapi import FastAPI
from pydantic import BaseModel
import requests
import base64
from PIL import Image
from io import BytesIO

app = FastAPI()

# 🔐 Tu API key de Stability AI
STABILITY_API_KEY = "sk-SvUaT8PRAdfe2hdYwti29Wc8bh5FbQZfBuJ4r4h3c3DlweyH"

# Modelo de entrada
class PromptInput(BaseModel):
    prompt: str

def generar_imagen_stability(prompt: str) -> str:
    files = {
        "prompt": (None, prompt),
        "output_format": (None, "png"),
    }

    response = requests.post(
        "https://api.stability.ai/v2beta/stable-image/generate/core",
        headers={
            "Authorization": f"Bearer {STABILITY_API_KEY}",
            "Accept": "application/json",
        },
        files=files,
    )

    if response.status_code == 200:
        data = response.json()
        return data["image"]  # Imagen codificada en base64
    else:
        raise Exception(f"Error Stability: {response.status_code}, {response.text}")

@app.post("/generate-image")
async def generate_image(data: PromptInput):
    try:
        image_base64 = generar_imagen_stability(data.prompt)
        return {
            "success": True,
            "image_base64": image_base64
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
