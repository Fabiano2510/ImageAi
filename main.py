from fastapi import FastAPI, Request
from pydantic import BaseModel
from diffusers import DiffusionPipeline
import torch
from PIL import Image
import uuid
import os

# Configuración inicial del modelo
model_name = "Qwen/Qwen-Image"

if torch.cuda.is_available():
    torch_dtype = torch.bfloat16
    device = "cuda"
else:
    torch_dtype = torch.float32
    device = "cpu"

pipe = DiffusionPipeline.from_pretrained(model_name, torch_dtype=torch_dtype)
pipe = pipe.to(device)

positive_magic = {
    "en": "Ultra HD, 4K, cinematic composition.",
}

aspect_ratios = {
    "1:1": (1328, 1328),
    "16:9": (1664, 928),
    "9:16": (928, 1664),
}

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"

@app.post("/generate")
async def generate_image(data: PromptRequest):
    prompt = data.prompt + positive_magic["en"]
    negative_prompt = ""
    width, height = aspect_ratios.get(data.aspect_ratio, aspect_ratios["16:9"])

    image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=50,
        true_cfg_scale=4.0,
        generator=torch.Generator(device=device).manual_seed(42)
    ).images[0]

    filename = f"image_{uuid.uuid4().hex[:8]}.jpg"
    image.save(filename, "JPEG")

    return {"message": "✅ Imagen generada", "filename": filename}
