import requests
import uuid

# Reemplaza con tu API key de DeepAI
API_KEY = "81d53499-be78-4580-8f73-b542389ff0b3"  # Consíguela gratis en https://deepai.org/

# Prompt para generar la imagen
prompt = "A majestic dragon flying over snowy mountains"

# Solicitud a la API de DeepAI
response = requests.post(
    "https://api.deepai.org/api/stable-diffusion",
    data={"text": prompt},
    headers={"api-key": API_KEY}
)

if response.status_code == 200:
    data = response.json()
    image_url = data["output_url"]
    print("Imagen generada en:", image_url)

    # Descargar imagen
    image_response = requests.get(image_url)
    filename = f"image_{uuid.uuid4().hex[:8]}.jpg"

    with open(filename, "wb") as f:
        f.write(image_response.content)

    print(f"Imagen guardada como {filename}")

else:
    print("Error al generar la imagen:")
    print(response.status_code, response.text)

