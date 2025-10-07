from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import logging
from functools import wraps
import hashlib
from werkzeug.exceptions import BadRequest
import google.generativeai as genai
import random
import requests  # ← AÑADIR ESTO
import json      # ← AÑADIR ESTO

from services.planner_service import PlannerService
from services.export_service import ExportService
from services.stats_service import StatsService
from services.auth_service import AuthService

# Configuración de la aplicación
app = Flask(__name__, static_folder="static")
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://mma-planner-pro.onrender.com",
            "http://localhost:5000", 
            "http://127.0.0.1:5000"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Clase para manejar la configuración de Gemini (MANTENER POR SI ACASO)
class GeminiManager:
    def __init__(self):
        self.model = None
        self.generation_config = None
        self.is_configured = False
        self.configure_gemini()
    
    def configure_gemini(self):
        """Configurar Google Gemini con parámetros optimizados"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY no encontrada en variables de entorno")
            self.is_configured = False
            return
        
        try:
            # Configurar Google Gemini - VERSIÓN COMPATIBLE
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            
            # Configurar generación
            self.generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 100,
            }
            
            self.is_configured = True
            logger.info("✅ Google Gemini configurado correctamente")
            
        except Exception as e:
            logger.error(f"Error configurando Gemini: {str(e)}")
            self.is_configured = False

# Inicializar el manager de Gemini (OPCIONAL)
gemini_manager = GeminiManager()

# Servicios
planner_service = PlannerService()
export_service = ExportService()
stats_service = StatsService()
auth_service = AuthService()

# Decorador para validación de entrada (MANTENER IGUAL)
def validate_json(required_fields=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    "status": "error", 
                    "message": "Content-Type debe ser application/json"
                }), 400
            
            data = request.get_json()
            if not data:
                return jsonify({
                    "status": "error", 
                    "message": "JSON vacío o inválido"
                }), 400
            
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data or data[field] is None]
                if missing_fields:
                    return jsonify({
                        "status": "error",
                        "message": f"Campos requeridos faltantes: {', '.join(missing_fields)}"
                    }), 400
            
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

# RUTAS PRINCIPALES (MANTENER TODAS IGUAL)
@app.route("/", methods=["GET"])
def home():
    """Servir la página principal"""
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/health", methods=["GET"])
def health_check():
    """Endpoint para verificar el estado de la API"""
    return jsonify({
        "status": "ok",
        "message": "MMA Training Planner API funcionando correctamente",
        "timestamp": datetime.now().isoformat(),
        "gemini_ai": "configured" if gemini_manager.is_configured else "not_configured"
    })

# RUTAS DE SESIONES (MANTENER TODAS IGUAL)
@app.route("/api/sessions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def add_session(data):
    """Agregar nueva sesión de entrenamiento"""
    session_data = planner_service.validate_session_data(data)
    planner_service.save_session(session_data)
    
    logger.info(f"Nueva sesión guardada: {session_data['tipo']} - {session_data['fecha']}")
    
    return jsonify({
        "status": "success",
        "message": "Sesión guardada exitosamente",
        "data": session_data
    }), 201

@app.route("/api/sessions", methods=["GET"])
@handle_errors
def get_sessions():
    """Obtener todas las sesiones"""
    sessions = planner_service.load_sessions()
    return jsonify({
        "status": "success",
        "data": sessions,
        "total": len(sessions)
    })

@app.route("/api/sessions/<int:session_id>", methods=["PUT"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def update_session(data, session_id):
    """Actualizar sesión existente"""
    session_data = planner_service.validate_session_data(data)
    updated_session = planner_service.update_session(session_id, session_data)
    
    if not updated_session:
        return jsonify({
            "status": "error",
            "message": "Sesión no encontrada"
        }), 404
    
    return jsonify({
        "status": "success",
        "message": "Sesión actualizada exitosamente",
        "data": updated_session
    })

@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
@handle_errors
def delete_session(session_id):
    """Eliminar sesión"""
    if planner_service.delete_session(session_id):
        return jsonify({
            "status": "success",
            "message": "Sesión eliminada exitosamente"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Sesión no encontrada"
        }), 404

# RUTAS DE ESTADÍSTICAS (MANTENER TODAS IGUAL)
@app.route("/api/stats/summary", methods=["GET"])
@handle_errors
def get_stats_summary():
    """Obtener resumen estadístico completo"""
    sessions = planner_service.load_sessions()
    stats = stats_service.calculate_comprehensive_stats(sessions)
    
    return jsonify({
        "status": "success",
        "data": stats
    })

@app.route("/api/stats/by-type", methods=["GET"])
@handle_errors
def get_stats_by_type():
    """Obtener estadísticas por tipo de entrenamiento"""
    sessions = planner_service.load_sessions()
    stats_by_type = stats_service.calculate_stats_by_type(sessions)
    
    return jsonify({
        "status": "success",
        "data": stats_by_type
    })

@app.route("/api/stats/monthly", methods=["GET"])
@handle_errors
def get_monthly_stats():
    """Obtener estadísticas mensuales"""
    sessions = planner_service.load_sessions()
    monthly_stats = stats_service.calculate_monthly_stats(sessions)
    
    return jsonify({
        "status": "success",
        "data": monthly_stats
    })

# RUTAS DE EXPORTACIÓN (MANTENER TODAS IGUAL)
@app.route("/api/export/csv", methods=["GET"])
@handle_errors
def export_csv():
    """Exportar sesiones a CSV"""
    sessions = planner_service.load_sessions()
    if not sessions:
        return jsonify({
            "status": "error",
            "message": "No hay sesiones para exportar"
        }), 400
    
    file_path = export_service.export_to_csv(sessions)
    return send_file(file_path, as_attachment=True, download_name="mma_training_sessions.csv")

@app.route("/api/export/excel", methods=["GET"])
@handle_errors
def export_excel():
    """Exportar sesiones a Excel"""
    sessions = planner_service.load_sessions()
    if not sessions:
        return jsonify({
            "status": "error",
            "message": "No hay sesiones para exportar"
        }), 400
    
    file_path = export_service.export_to_excel(sessions)
    return send_file(file_path, as_attachment=True, download_name="mma_training_sessions.xlsx")

@app.route("/api/export/pdf", methods=["GET"])
@handle_errors
def export_pdf():
    """Exportar sesiones a PDF"""
    sessions = planner_service.load_sessions()
    if not sessions:
        return jsonify({
            "status": "error",
            "message": "No hay sesiones para exportar"
        }), 400
    
    stats = stats_service.calculate_comprehensive_stats(sessions)
    file_path = export_service.export_to_pdf(sessions, stats)
    return send_file(file_path, as_attachment=True, download_name="mma_training_report.pdf")

# RUTAS DE AUTENTICACIÓN (MANTENER IGUAL)
@app.route("/api/auth/login", methods=["POST"])
@handle_errors
@validate_json(required_fields=["username", "password"])
def login(data):
    """Login simple"""
    if auth_service.authenticate(data["username"], data["password"]):
        token = auth_service.generate_token(data["username"])
        return jsonify({
            "status": "success",
            "message": "Login exitoso",
            "token": token,
            "user": data["username"]
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Credenciales inválidas"
        }), 401

# RUTAS DE IA - SUGERENCIAS INTELIGENTES CON GEMINI API DIRECTA (NUEVA VERSIÓN)
@app.route("/api/ai-suggestions", methods=["POST"])
@handle_errors
def ai_suggestions():
    """Generar sugerencias de entrenamiento usando IA - API DIRECTA"""
    data = request.get_json()
    sessions = data.get("sessions", [])
    
    if not sessions:
        return jsonify({
            "status": "error", 
            "message": "No hay sesiones para analizar"
        }), 400

    # Convierte las sesiones a texto legible
    prompt = "Eres un entrenador profesional de MMA. Analiza estas sesiones y da UNA sugerencia específica para mejorar (máximo 2 líneas):\n"
    for s in sessions[-6:]:
        prompt += f"- {s.get('tipo', 'desconocido')}: {s.get('tiempo', 0)}min, Intensidad: {s.get('intensidad', 'Media')}\n"

    try:
        # Para evitar errores si no hay API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({
                "status": "success",
                "sugerencia": "⚠️ Configura tu API key de Google Gemini"
            })
            
        # LLAMADA DIRECTA A GEMINI API - 100% FUNCIONAL
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": 100,
                "temperature": 0.7
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            suggestion = result['candidates'][0]['content']['parts'][0]['text'].strip()
            
            return jsonify({
                "status": "success",
                "sugerencia": suggestion
            })
        else:
            raise Exception(f"API error: {response.status_code}")

    except Exception as e:
        logger.error(f"Error Gemini API: {str(e)}")
        
        # FALLBACK INTELIGENTE (que SÍ funciona)
        total_time = sum(s.get('tiempo', 0) for s in sessions)
        tipos = [s.get('tipo', '') for s in sessions]
        
        if total_time > 120:
            suggestion = "💪 Buen volumen de entrenamiento. Considera agregar un día de descanso activo con movilidad."
        elif "Grappling" in tipos and "Boxeo" not in tipos:
            suggestion = "🥊 Balancea tu entrenamiento agregando sesiones de striking."
        elif len(sessions) < 3:
            suggestion = "🔥 Buena base. Mantén la consistencia y aumenta gradualmente la intensidad."
        else:
            suggestion = "💡 Varía entre grappling y striking para desarrollo balanceado."
        
        return jsonify({
            "status": "success",
            "sugerencia": suggestion
        })

# Ruta adicional para verificar estado de Gemini (MANTENER)
@app.route("/api/ai-status", methods=["GET"])
@handle_errors
def ai_status():
    """Verificar el estado de la integración con Gemini AI"""
    status = {
        "gemini_configured": gemini_manager.is_configured,
        "api_key_present": bool(os.getenv("GEMINI_API_KEY")),
        "status": "active" if gemini_manager.is_configured else "inactive"
    }
    
    return jsonify({
        "status": "success",
        "data": status
    })
    
# Manejo de errores globales (MANTENER)
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "message": "Endpoint no encontrado"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "status": "error",
        "message": "Método no permitido"
    }), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "status": "error",
        "message": "Error interno del servidor"
    }), 500

if __name__ == "__main__":
    # Crear directorios necesarios
    os.makedirs("exports", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # Ejecutar en modo desarrollo
    app.run(debug=True, host="0.0.0.0", port=5000)

