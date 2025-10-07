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

# Servicios
planner_service = PlannerService()
export_service = ExportService()
stats_service = StatsService()
auth_service = AuthService()

# Decorador para validación de entrada
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

# RUTAS PRINCIPALES
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
        "timestamp": datetime.now().isoformat()
    })

# RUTAS DE SESIONES
@app.route("/api/sessions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def add_session(data):
    """Agregar nueva sesión de entrenamiento"""
    # Validar y procesar datos
    session_data = planner_service.validate_session_data(data)
    
    # Guardar sesión
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

# RUTAS DE ESTADÍSTICAS
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

# RUTAS DE EXPORTACIÓN
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

# RUTAS DE AUTENTICACIÓN (OPCIONAL)
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

# RUTAS DE IA - SUGERENCIAS INTELIGENTES CON GOOGLE GEMINI
@app.route("/api/ai-suggestions", methods=["POST"])
@handle_errors
def ai_suggestions():
    data = request.get_json()
    sessions = data.get("sessions", [])
    
    if not sessions:
        return jsonify({
            "status": "error", 
            "message": "No hay sesiones para analizar"
        }), 400

    # Convierte las sesiones a texto legible
    prompt = """Eres un entrenador profesional de MMA. Analiza estas sesiones de entrenamiento y da UNA sugerencia específica para mejorar. 
Sé directo, técnico y conciso (máximo 2 líneas). No des consejos genéricos.

Sesiones:
"""
    for s in sessions[-8:]:  # Últimas 8 sesiones
        fecha = s.get('fecha', '')
        tipo = s.get('tipo', 'desconocido')
        tiempo = s.get('tiempo', 0)
        intensidad = s.get('intensidad', 'Media')
        prompt += f"- {fecha}: {tipo} - {tiempo}min, Intensidad: {intensidad}\n"

    try:
        # Para evitar errores si no hay API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({
                "status": "success",
                "sugerencia": "⚠️ Configura tu API key de Google Gemini para obtener sugerencias IA"
            })
            
        # Configurar Google Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        response = model.generate_content(prompt)
        suggestion = response.text.strip()
        
        return jsonify({
            "status": "success",
            "sugerencia": suggestion
        })

    except Exception as e:
        logger.error(f"Error Gemini: {str(e)}")
        
        # Fallback inteligente basado en las sesiones
        total_time = sum(s.get('tiempo', 0) for s in sessions)
        tipos = [s.get('tipo', '') for s in sessions]
        
        fallback_suggestions = [
            "💡 Varía entre grappling y striking para desarrollo balanceado",
            "🔥 Mantén la consistencia y agrega días de descanso activo",
            "🥊 Enfócate en la técnica antes que la intensidad para prevenir lesiones",
            "💪 Incrementa gradualmente la duración de tus sesiones",
            "🔄 Incluye entrenamiento de movilidad para mejorar flexibilidad",
            "⏱️ Controla los tiempos de descanso entre rounds",
            "🏋️ Agrega ejercicios de fuerza para mejorar tu poder",
            "🧘 No descuides el trabajo de flexibilidad y recuperación"
        ]
        
        # Sugerencia más específica basada en los datos
        if total_time > 120:
            suggestion = "💪 Buen volumen de entrenamiento. Considera agregar un día de descanso activo con movilidad."
        elif "Grappling" in tipos and "Boxeo" not in tipos:
            suggestion = "🥊 Balancea tu entrenamiento agregando sesiones de striking para desarrollo completo."
        elif len(sessions) < 3:
            suggestion = "🔥 Buena base. Mantén la consistencia y ve incrementando gradualmente la intensidad."
        else:
            suggestion = random.choice(fallback_suggestions)
        
        return jsonify({
            "status": "success",
            "sugerencia": suggestion
        })
    
# Manejo de errores globales
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
