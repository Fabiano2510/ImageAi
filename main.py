from fastapi import FastAPI, Request
from pydantic import BaseModel
from google.cloud import translate_v2 as translate
import requests
import base64
from PIL import Image
from io import BytesIO
import os

app = FastAPI()

# 🔐 Clave API de Stability
STABILITY_API_KEY = "TU_API_KEY_STABILITY"

# Traductor de Google Cloud
translator = translate.Client()

# Modelo de entrada
class PromptInput(BaseModel):
    prompt: str

def traducir_a_ingles(texto: str) -> str:
    result = translator.translate(texto, target_language="en")
    return result["translatedText"]

def generar_imagen_stability(prompt_ingles: str) -> str:
    files = {
        "prompt": (None, prompt_ingles),
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
        return data["image"]  # Base64 string
    else:
        raise Exception(f"Error Stability: {response.status_code}, {response.text}")

@app.post("/generate-image")
async def generate_image(data: PromptInput):
    try:
        prompt_original = data.prompt
        prompt_en = traducir_a_ingles(prompt_original)
        image_base64 = generar_imagen_stability(prompt_en)

        return {
            "success": True,
            "translated_prompt": prompt_en,
            "image_base64": image_base64
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
