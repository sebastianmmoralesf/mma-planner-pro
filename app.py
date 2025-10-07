from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import logging
from functools import wraps
import requests # Se importa requests para las llamadas a la API
import random

# --- Inicio del Mock de Servicios (para que el código sea ejecutable por sí solo) ---
class MockService:
    def __init__(self):
        self._sessions = {
            1: {'id': 1, 'fecha': '2024-10-01', 'tipo': 'Grappling', 'tiempo': 90, 'intensidad': 'Alta', 'notas': 'Técnica de sumisión'},
            2: {'id': 2, 'fecha': '2024-10-02', 'tipo': 'Boxeo', 'tiempo': 60, 'intensidad': 'Media', 'notas': 'Trabajo de pies'},
        }
        self._next_id = 3
    def validate_session_data(self, data): return data
    def save_session(self, session_data): self._sessions[self._next_id] = session_data; self._next_id += 1; return session_data
    def load_sessions(self): return list(self._sessions.values())
    def update_session(self, session_id, session_data): self._sessions[session_id] = session_data; return session_data
    def delete_session(self, session_id):
        if session_id in self._sessions: del self._sessions[session_id]; return True
        return False
    def calculate_comprehensive_stats(self, sessions): return {"total_sessions": len(sessions), "total_time": sum(s.get('tiempo', 0) for s in sessions)}
    def calculate_stats_by_type(self, sessions): return {s.get('tipo', 'G'): s.get('tipo', 'G') for s in sessions}
    def calculate_monthly_stats(self, sessions): return {"October": len(sessions)}
    def export_to_csv(self, sessions): path = os.path.join("exports", "data.csv"); open(path, "w").close(); return path
    def export_to_excel(self, sessions): path = os.path.join("exports", "data.xlsx"); open(path, "w").close(); return path
    def export_to_pdf(self, sessions, stats): path = os.path.join("exports", "data.pdf"); open(path, "w").close(); return path
    def authenticate(self, u, p): return True
    def generate_token(self, u): return "fake-token"

planner_service = MockService()
export_service = MockService()
stats_service = MockService()
auth_service = MockService()
# --- Fin del Mock de Servicios ---

app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiManager:
    """Clase para manejar la comunicación con la API REST de Gemini"""
    
    def __init__(self):
        self.api_key = None
        self.is_configured = False
        self.configure_gemini()

    def configure_gemini(self):
        """Verifica la API Key de Gemini desde las variables de entorno"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY no encontrada en variables de entorno.")
            self.is_configured = False
        else:
            self.is_configured = True
            logger.info("✅ Gemini API Key encontrada. El servicio de IA está listo.")

    def get_suggestion(self, prompt):
        """Obtener sugerencia de Gemini a través de una llamada a la API REST"""
        if not self.is_configured:
            raise Exception("Gemini no está configurado por falta de API Key.")

        # ==============================================================================
        # SOLUCIÓN: Usar el nombre del modelo 'gemini-1.0-pro' en la URL.
        # ==============================================================================
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={self.api_key}"
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 150
            }
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            suggestion = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not suggestion:
                raise Exception("La respuesta de la API de Gemini no contiene una sugerencia válida.")
            return suggestion.strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la llamada a la API de Gemini: {e}")
            raise Exception(f"No se pudo conectar con el servicio de IA. Error: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"Error al procesar la respuesta de Gemini. Formato inesperado. {e}")
            raise Exception("La respuesta del servicio de IA tuvo un formato inesperado.")

gemini_manager = GeminiManager()

def validate_json(required_fields=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json: return jsonify({"status": "error", "message": "Content-Type debe ser application/json"}), 400
            data = request.get_json()
            if not data: return jsonify({"status": "error", "message": "JSON vacío o inválido"}), 400
            if required_fields:
                missing = [field for field in required_fields if field not in data or data[field] is None]
                if missing: return jsonify({"status": "error", "message": f"Campos requeridos faltantes: {', '.join(missing)}"}), 400
            return f(data, *args, **kwargs)
        return decorated_function
    return decorator

def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error interno: {str(e)}")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500
    return decorated_function

# --- El resto de las rutas y la lógica permanecen sin cambios ---
@app.route("/", methods=["GET"])
def home():
    return "<h1>MMA Planner Pro API</h1>"

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "gemini_ai": "configured" if gemini_manager.is_configured else "not_configured"
    })

@app.route("/api/sessions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def add_session(data):
    session = planner_service.save_session(data)
    return jsonify({"status": "success", "data": session}), 201

@app.route("/api/sessions", methods=["GET"])
@handle_errors
def get_sessions():
    sessions = planner_service.load_sessions()
    return jsonify({"status": "success", "data": sessions})

@app.route("/api/ai-suggestions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["sessions"])
def ai_suggestions(data):
    sessions = data.get("sessions", [])
    if not sessions:
        return jsonify({"status": "error", "message": "No hay sesiones para analizar"}), 400
    prompt = "Eres un entrenador de MMA. Analiza estas sesiones y da UNA sugerencia concisa:\n"
    for s in sessions:
        prompt += f"- {s.get('fecha')}: {s.get('tipo')} - {s.get('tiempo')}min\n"
    prompt += "\nSugerencia:"
    try:
        if not gemini_manager.is_configured:
            return jsonify({"status": "success", "sugerencia": "⚠️ Configura GEMINI_API_KEY para obtener sugerencias IA.", "tipo": "info"})
        suggestion = gemini_manager.get_suggestion(prompt)
        return jsonify({"status": "success", "sugerencia": suggestion, "tipo": "ia"})
    except Exception as e:
        fallback = generate_fallback_suggestion(sessions)
        return jsonify({"status": "success", "sugerencia": fallback, "tipo": "fallback"})

def generate_fallback_suggestion(sessions):
    return "💡 Mantén la consistencia. Varía entre grappling y striking para un desarrollo balanceado."

if __name__ == "__main__":
    os.makedirs("exports", exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)

