from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

DEEP_AI_API_KEY = "81d53499-be78-4580-8f73-b542389ff0b3"  # Consíguela gratis en https://deepai.org

@app.post("/generate-image")
async def generate_image(data: PromptRequest):
    response = requests.post(
        "https://api.deepai.org/api/stable-diffusion",
        data={"text": data.prompt},
        headers={"api-key": DEEP_AI_API_KEY}
    )

    if response.status_code == 200:
        output = response.json()
        return {"success": True, "image_url": output["output_url"]}
    else:
        return {
            "success": False,
            "status": response.status_code,
            "error": response.text
        }
