import requests

API_TOKEN = "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"
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

payload = {
    "inputs": "A highly realistic futuristic AI assistant standing in a sleek tech room, photorealistic"
}

response = requests.post(
    "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1",
    headers=headers,
    json=payload
)

if response.status_code == 200:
    with open("imagen_generada.png", "wb") as f:
        f.write(response.content)
    print("Imagen guardada como imagen_generada.png")
else:
    print("Error:", response.status_code, response.text)
