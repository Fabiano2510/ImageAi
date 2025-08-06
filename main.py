from flask import Flask, request, jsonify
from google.cloud import translate_v2 as translate
import requests
import base64
from PIL import Image
from io import BytesIO
import os

app = Flask(__name__)

# Configura tu clave de Stability AI
STABILITY_API_KEY = "sk-SvUaT8PRAdfe2hdYwti29Wc8bh5FbQZfBuJ4r4h3c3DlweyH"

# Inicializa el traductor de Google
translator = translate.Client()

def traducir_a_ingles(texto):
    resultado = translator.translate(texto, target_language='en')
    return resultado['translatedText']

def generar_imagen_stability(prompt_ingles):
    files = {
        "prompt": (None, prompt_ingles),
        "output_format": (None, "png")
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
        return data["image"]  # Imagen en base64
    else:
        raise Exception(f"Error Stability: {response.status_code}, {response.text}")

@app.route('/generate-image', methods=['POST'])
def generar_imagen():
    data = request.get_json()
    prompt = data.get("prompt")

    if not prompt:
        return jsonify({"error": "No se proporcionó ningún prompt."}), 400

    try:
        prompt_traducido = traducir_a_ingles(prompt)
        print(f"[🔤] Prompt traducido: {prompt_traducido}")

        imagen_base64 = generar_imagen_stability(prompt_traducido)
        return jsonify({
            "success": True,
            "image_base64": imagen_base64,
            "translated_prompt": prompt_traducido
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Establece la ruta de credenciales de Google
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "ruta/a/tu/credenciales.json"
    app.run(host='0.0.0.0', port=5000)
