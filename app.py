import os
import json
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
app = Flask(__name__)
CORS(app)
app.config["JSON_AS_ASCII"] = False

logging.basicConfig(level=logging.INFO)

# Cargar clave API de Gemini desde entorno
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("⚠️ Falta la variable de entorno GEMINI_API_KEY")

# ============================================================
# DECORADORES DE VALIDACIÓN
# ============================================================
def validate_json(required_fields=None):
    """Valida que la solicitud contenga JSON con los campos requeridos."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "El cuerpo debe ser JSON"}), 400
            data = request.get_json()
            if required_fields:
                faltantes = [f for f in required_fields if f not in data]
                if faltantes:
                    return jsonify({
                        "error": f"Faltan campos requeridos: {', '.join(faltantes)}"
                    }), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================
# FUNCIÓN PRINCIPAL: OBTENER SUGERENCIAS IA
# ============================================================
@app.route("/api/ai-suggestions", methods=["POST"])
@validate_json(required_fields=["sessions"])
def ai_suggestions():
    try:
        data = request.get_json()
        sessions = data.get("sessions", [])

        if not sessions:
            return jsonify({"error": "No hay sesiones registradas"}), 400

        # Tomar las últimas 6 sesiones
        recent = sessions[-6:]

        # Crear prompt claro y breve para Gemini
        prompt = (
            "Eres un entrenador de MMA experto. Analiza las siguientes sesiones "
            "y genera una sugerencia personalizada de entrenamiento:\n\n"
        )
        for s in recent:
            prompt += f"- {s.get('fecha', '?')}: {s.get('tipo', 'Desconocido')} | {s.get('tiempo', '?')} min | Intensidad {s.get('intensidad', 'N/A')}\n"
        prompt += "\nEn base a estas, sugiere el siguiente paso lógico en el entrenamiento."

        # Petición directa a Gemini API REST
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 150, "temperature": 0.7}
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        suggestion = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not suggestion:
            raise ValueError("Gemini no devolvió texto")

        return jsonify({"suggestion": suggestion.strip()})

    except requests.exceptions.Timeout:
        logging.error("⏱️ Timeout al conectar con Gemini")
        return jsonify({"suggestion": "Gemini no respondió a tiempo. Intenta más tarde."}), 504
    except Exception as e:
        logging.exception("⚠️ Error en /api/ai-suggestions")
        return jsonify({"suggestion": "No se pudo generar la sugerencia. Intenta más tarde."}), 500

# ============================================================
# ENDPOINT DE PRUEBA BÁSICO
# ============================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "MMA Planner Pro backend activo 🥋"})

# ============================================================
# INICIO DE LA APLICACIÓN
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
