from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import logging
from functools import wraps
import requests # Se importa requests para las llamadas a la API
import random

# --- Inicio del Mock de Servicios (para que el código sea ejecutable por sí solo) ---
# En tu proyecto real, deberías eliminar este bloque y usar tus propios módulos de servicio.
class MockService:
    def __init__(self):
        self._sessions = {
            1: {'id': 1, 'fecha': '2024-10-01', 'tipo': 'Grappling', 'tiempo': 90, 'intensidad': 'Alta', 'notas': 'Técnica de sumisión'},
            2: {'id': 2, 'fecha': '2024-10-02', 'tipo': 'Boxeo', 'tiempo': 60, 'intensidad': 'Media', 'notas': 'Trabajo de pies'},
        }
        self._next_id = 3

    def validate_session_data(self, data):
        data['fecha'] = data.get('fecha', '')
        data['tipo'] = data.get('tipo', 'General')
        data['tiempo'] = int(data.get('tiempo', 0))
        data['intensidad'] = data.get('intensidad', 'Media')
        data['notas'] = data.get('notas', '')
        return data

    def save_session(self, session_data):
        session_data['id'] = self._next_id
        self._sessions[self._next_id] = session_data
        self._next_id += 1
        return session_data

    def load_sessions(self):
        return list(self._sessions.values())

    def update_session(self, session_id, session_data):
        if session_id in self._sessions:
            session_data['id'] = session_id
            self._sessions[session_id] = session_data
            return session_data
        return None

    def delete_session(self, session_id):
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def calculate_comprehensive_stats(self, sessions):
        return {"total_sessions": len(sessions), "total_time": sum(s.get('tiempo', 0) for s in sessions)}

    def calculate_stats_by_type(self, sessions):
        stats = {}
        for s in sessions:
            tipo = s.get('tipo', 'General')
            stats[tipo] = stats.get(tipo, 0) + 1
        return stats

    def calculate_monthly_stats(self, sessions):
        return {"October": len(sessions)}

    def export_to_csv(self, sessions):
        path = os.path.join("exports", "mma_training_sessions.csv")
        with open(path, "w") as f:
            f.write("fecha,tipo,tiempo\n")
            for s in sessions:
                f.write(f"{s['fecha']},{s['tipo']},{s['tiempo']}\n")
        return path

    def export_to_excel(self, sessions):
        path = os.path.join("exports", "mma_training_sessions.xlsx")
        with open(path, "w") as f:
            f.write("Excel file content")
        return path

    def export_to_pdf(self, sessions, stats):
        path = os.path.join("exports", "mma_training_report.pdf")
        with open(path, "w") as f:
            f.write("PDF file content")
        return path
        
    def authenticate(self, username, password):
        return username == "admin" and password == "admin"
        
    def generate_token(self, username):
        return f"fake-token-for-{username}"

planner_service = MockService()
export_service = MockService()
stats_service = MockService()
auth_service = MockService()
# --- Fin del Mock de Servicios ---


# Configuración de la aplicación
app = Flask(__name__, static_folder="static")
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "https://mma-planner-pro.onrender.com",
                "http://localhost:5000",
                "http://127.0.0.1:5000"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    }
)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# SECCIÓN MODIFICADA: GeminiManager ahora usa la API REST en lugar del SDK
# ==============================================================================
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
            logger.warning("GEMINI_API_KEY no encontrada en variables de entorno. Las sugerencias de IA no funcionarán.")
            self.is_configured = False
        else:
            self.is_configured = True
            logger.info("✅ Gemini API Key encontrada. El servicio de IA está listo.")

    def get_suggestion(self, prompt):
        """Obtener sugerencia de Gemini a través de una llamada a la API REST"""
        if not self.is_configured:
            raise Exception("Gemini no está configurado por falta de API Key.")

        # Endpoint oficial de la API para el modelo gemini-pro
        # Nota: Usamos v1beta, que es el recomendado para este modelo.
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }

        # Payload con el prompt y la configuración de generación
        # Nota: los nombres de los parámetros en JSON usan camelCase (ej. topP, maxOutputTokens)
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 150
            }
        }

        try:
            # Realizar la petición POST con un timeout de 30 segundos
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            
            # Lanzar un error si la respuesta no fue exitosa (ej. 4xx, 5xx)
            response.raise_for_status()
            
            # Procesar la respuesta JSON
            result = response.json()
            
            # Extraer el texto de la respuesta de forma segura
            # La estructura es: result['candidates'][0]['content']['parts'][0]['text']
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
# ==============================================================================
# FIN DE LA SECCIÓN MODIFICADA
# ==============================================================================


# Inicializar el manager de Gemini
gemini_manager = GeminiManager()

# Decoradores (sin cambios)
def validate_json(required_fields=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({"status": "error", "message": "Content-Type debe ser application/json"}), 400
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "JSON vacío o inválido"}), 400
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data or data[field] is None]
                if missing_fields:
                    return jsonify({"status": "error", "message": f"Campos requeridos faltantes: {', '.join(missing_fields)}"}), 400
            return f(data, *args, **kwargs)
        return decorated_function
    return decorator

def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.error(f"Error de validación: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            logger.error(f"Error interno: {str(e)}")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500
    return decorated_function

# --- El resto del código permanece exactamente igual ---

# RUTAS PRINCIPALES
@app.route("/", methods=["GET"])
def home():
    if not os.path.exists(os.path.join(app.static_folder, "index.html")):
        return "<h1>MMA Planner Pro</h1><p>API está funcionando. Archivo estático no encontrado.</p>"
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "MMA Training Planner API funcionando correctamente",
        "timestamp": datetime.now().isoformat(),
        "gemini_ai": "configured" if gemini_manager.is_configured else "not_configured"
    })


# RUTAS DE SESIONES
@app.route("/api/sessions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def add_session(data):
    session_data = planner_service.validate_session_data(data)
    planner_service.save_session(session_data)
    logger.info(f"Nueva sesión guardada: {session_data['tipo']} - {session_data['fecha']}")
    return jsonify({"status": "success", "message": "Sesión guardada exitosamente", "data": session_data}), 201


@app.route("/api/sessions", methods=["GET"])
@handle_errors
def get_sessions():
    sessions = planner_service.load_sessions()
    return jsonify({"status": "success", "data": sessions, "total": len(sessions)})


@app.route("/api/sessions/<int:session_id>", methods=["PUT"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def update_session(data, session_id):
    session_data = planner_service.validate_session_data(data)
    updated_session = planner_service.update_session(session_id, session_data)
    if not updated_session:
        return jsonify({"status": "error", "message": "Sesión no encontrada"}), 404
    return jsonify({"status": "success", "message": "Sesión actualizada exitosamente", "data": updated_session})


@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
@handle_errors
def delete_session(session_id):
    if planner_service.delete_session(session_id):
        return jsonify({"status": "success", "message": "Sesión eliminada exitosamente"})
    else:
        return jsonify({"status": "error", "message": "Sesión no encontrada"}), 404


# RUTAS DE ESTADÍSTICAS
@app.route("/api/stats/summary", methods=["GET"])
@handle_errors
def get_stats_summary():
    sessions = planner_service.load_sessions()
    stats = stats_service.calculate_comprehensive_stats(sessions)
    return jsonify({"status": "success", "data": stats})


@app.route("/api/stats/by-type", methods=["GET"])
@handle_errors
def get_stats_by_type():
    sessions = planner_service.load_sessions()
    stats_by_type = stats_service.calculate_stats_by_type(sessions)
    return jsonify({"status": "success", "data": stats_by_type})


@app.route("/api/stats/monthly", methods=["GET"])
@handle_errors
def get_monthly_stats():
    sessions = planner_service.load_sessions()
    monthly_stats = stats_service.calculate_monthly_stats(sessions)
    return jsonify({"status": "success", "data": monthly_stats})


# RUTAS DE EXPORTACIÓN
@app.route("/api/export/csv", methods=["GET"])
@handle_errors
def export_csv():
    sessions = planner_service.load_sessions()
    if not sessions:
        return jsonify({"status": "error", "message": "No hay sesiones para exportar"}), 400
    file_path = export_service.export_to_csv(sessions)
    return send_file(file_path, as_attachment=True, download_name="mma_training_sessions.csv")


@app.route("/api/export/excel", methods=["GET"])
@handle_errors
def export_excel():
    sessions = planner_service.load_sessions()
    if not sessions:
        return jsonify({"status": "error", "message": "No hay sesiones para exportar"}), 400
    file_path = export_service.export_to_excel(sessions)
    return send_file(file_path, as_attachment=True, download_name="mma_training_sessions.xlsx")


@app.route("/api/export/pdf", methods=["GET"])
@handle_errors
def export_pdf():
    sessions = planner_service.load_sessions()
    if not sessions:
        return jsonify({"status": "error", "message": "No hay sesiones para exportar"}), 400
    stats = stats_service.calculate_comprehensive_stats(sessions)
    file_path = export_service.export_to_pdf(sessions, stats)
    return send_file(file_path, as_attachment=True, download_name="mma_training_report.pdf")


# RUTAS DE AUTENTICACIÓN
@app.route("/api/auth/login", methods=["POST"])
@handle_errors
@validate_json(required_fields=["username", "password"])
def login(data):
    if auth_service.authenticate(data["username"], data["password"]):
        token = auth_service.generate_token(data["username"])
        return jsonify({"status": "success", "message": "Login exitoso", "token": token, "user": data["username"]})
    else:
        return jsonify({"status": "error", "message": "Credenciales inválidas"}), 401


# RUTAS DE IA
@app.route("/api/ai-suggestions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["sessions"])
def ai_suggestions(data):
    sessions = data.get("sessions", [])
    if not sessions:
        return jsonify({"status": "error", "message": "No hay sesiones para analizar"}), 400

    prompt = """Eres un entrenador profesional de MMA. Analiza estas sesiones de entrenamiento y da UNA sugerencia específica para mejorar. Sé directo, técnico y conciso (máximo 100 palabras). No des consejos genéricos. Enfócate en aspectos técnicos, tácticos o de periodización.\n\nSesiones recientes: """
    for s in sessions[-10:]:
        prompt += f"- {s.get('fecha', '')}: {s.get('tipo', 'desconocido')} - {s.get('tiempo', 0)}min, Intensidad: {s.get('intensidad', 'Media')}"
        if s.get('notas', ''):
            prompt += f", Notas: {s.get('notas', '')}"
        prompt += "\n"
    prompt += "\nSugerencia específica:"

    try:
        if not gemini_manager.is_configured:
            gemini_manager.configure_gemini() # Reintentar configurar por si la API key fue agregada
        if not gemini_manager.is_configured:
            return jsonify({"status": "success", "sugerencia": "⚠️ Configura tu GEMINI_API_KEY en las variables de entorno para obtener sugerencias IA", "tipo": "info"})

        suggestion = gemini_manager.get_suggestion(prompt)
        logger.info("Sugerencia IA generada exitosamente vía API REST.")
        return jsonify({"status": "success", "sugerencia": suggestion, "tipo": "ia"})

    except Exception as e:
        logger.error(f"Error al obtener sugerencia de IA: {e}")
        fallback_suggestion = generate_fallback_suggestion(sessions)
        return jsonify({"status": "success", "sugerencia": fallback_suggestion, "tipo": "fallback"})

def generate_fallback_suggestion(sessions):
    if not sessions:
        return "💡 Comienza registrando tus primeras sesiones de entrenamiento para obtener sugerencias personalizadas."
    tipos = [s.get('tipo', '').lower() for s in sessions]
    grappling_count = sum(1 for t in tipos if any(x in t for x in ['grappling', 'jiu', 'bjj']))
    striking_count = sum(1 for t in tipos if any(x in t for x in ['boxeo', 'striking', 'muay']))
    if grappling_count > striking_count * 2:
        return "🥊 Balancea tu entrenamiento agregando más sesiones de striking para desarrollo completo en MMA."
    if striking_count > grappling_count * 2:
        return "🤼 Enfócate en mejorar tu grappling. Agrega sesiones de BJJ o wrestling para equilibrio."
    fallback_suggestions = ["💡 Varía entre grappling y striking para desarrollo balanceado", "🔥 Mantén la consistencia y agrega días de descanso activo"]
    return random.choice(fallback_suggestions)


@app.route("/api/ai-status", methods=["GET"])
@handle_errors
def ai_status():
    status = {"gemini_configured": gemini_manager.is_configured, "api_key_present": bool(os.getenv("GEMINI_API_KEY")), "status": "active" if gemini_manager.is_configured else "inactive"}
    return jsonify({"status": "success", "data": status})


# MANEJO DE ERRORES GLOBALES
@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Endpoint no encontrado"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"status": "error", "message": "Error interno del servidor"}), 500


if __name__ == "__main__":
    os.makedirs("exports", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port) # debug=False es mejor para producción

