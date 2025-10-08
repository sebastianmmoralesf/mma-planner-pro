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

# Clase para manejar la configuración de Gemini
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
            self.model = genai.GenerativeModel('gemini-pro')  # ← ESTE SÍ FUNCIONA
            
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
    
    def get_suggestion(self, prompt):
        """Obtener sugerencia de Gemini"""
        if not self.is_configured or not self.model:
            raise Exception("Gemini no está configurado")
        
        response = self.model.generate_content(
            prompt,
            generation_config=self.generation_config
        )
        return response.text.strip()

# Inicializar el manager de Gemini
gemini_manager = GeminiManager()

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
        "timestamp": datetime.now().isoformat(),
        "gemini_ai": "configured" if gemini_manager.is_configured else "not_configured"
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
@validate_json(required_fields=["sessions"])
def ai_suggestions(data):
    """Generar sugerencias de entrenamiento usando IA"""
    sessions = data.get("sessions", [])
    
    if not sessions:
        return jsonify({
            "status": "error", 
            "message": "No hay sesiones para analizar"
        }), 400

    # Construir prompt mejorado
    prompt = """Eres un entrenador profesional de MMA. Analiza estas sesiones de entrenamiento y da UNA sugerencia específica para mejorar. 
Sé directo, técnico y conciso (máximo 100 palabras). No des consejos genéricos. Enfócate en aspectos técnicos, tácticos o de periodización.

Sesiones recientes:
"""
    for s in sessions[-10:]:  # Últimas 10 sesiones para mejor contexto
        fecha = s.get('fecha', '')
        tipo = s.get('tipo', 'desconocido')
        tiempo = s.get('tiempo', 0)
        intensidad = s.get('intensidad', 'Media')
        notas = s.get('notas', '')
        
        prompt += f"- {fecha}: {tipo} - {tiempo}min, Intensidad: {intensidad}"
        if notas:
            prompt += f", Notas: {notas}"
        prompt += "\n"

    prompt += "\nSugerencia específica:"

    try:
        # Verificar configuración de Gemini
        if not gemini_manager.is_configured:
            # Intentar reconfigurar por si la API key fue agregada después
            gemini_manager.configure_gemini()
            
        if not gemini_manager.is_configured:
            return jsonify({
                "status": "success",
                "sugerencia": "⚠️ Configura tu GEMINI_API_KEY en las variables de entorno para obtener sugerencias IA",
                "tipo": "info"
            })

        # Generar sugerencia con Gemini usando la configuración optimizada
        suggestion = gemini_manager.get_suggestion(prompt)
        
        logger.info(f"Sugerencia IA generada exitosamente")
        
        return jsonify({
            "status": "success",
            "sugerencia": suggestion,
            "tipo": "ia"
        })

    except Exception as e:
        logger.error(f"Error Gemini: {str(e)}")
        
        # Fallback inteligente mejorado basado en las sesiones
        fallback_suggestion = generate_fallback_suggestion(sessions)
        
        return jsonify({
            "status": "success",
            "sugerencia": fallback_suggestion,
            "tipo": "fallback"
        })
@app.route("/api/quick-advice", methods=["POST"])
@handle_errors
def quick_advice():
    """Endpoint específico para el botón de consejo rápido"""
    sessions = planner_service.load_sessions()
    
    if not sessions:
        return jsonify({
            "status": "success",
            "advice": "🎯 Comienza registrando tus primeras sesiones para obtener consejos personalizados!",
            "type": "info"
        })
    
    # Usar la misma lógica que ai-suggestions pero simplificada
    prompt = """Eres un entrenador de MMA. Da UN consejo específico y corto (máximo 60 palabras) 
basado en estas sesiones. Sé directo y técnico:

Sesiones recientes:
"""
    for s in sessions[-5:]:  # Solo últimas 5 para ser más rápido
        fecha = s.get('fecha', '')
        tipo = s.get('tipo', 'desconocido')
        tiempo = s.get('tiempo', 0)
        prompt += f"- {fecha}: {tipo} - {tiempo}min\n"

    prompt += "\nConsejo rápido:"

    try:
        if not gemini_manager.is_configured:
            gemini_manager.configure_gemini()
            
        if gemini_manager.is_configured:
            suggestion = gemini_manager.get_suggestion(prompt)
            return jsonify({
                "status": "success",
                "advice": suggestion,
                "type": "ia"
            })
    except Exception as e:
        logger.error(f"Error IA en quick-advice: {str(e)}")

    # Fallback automático si falla la IA
    fallback_advice = generate_fallback_suggestion(sessions)
    return jsonify({
        "status": "success", 
        "advice": fallback_advice,
        "type": "fallback"
    })

def generate_fallback_suggestion(sessions):
    """Generar sugerencia de fallback inteligente basada en los datos"""
    if not sessions:
        return "💡 Comienza registrando tus primeras sesiones de entrenamiento para obtener sugerencias personalizadas."
    
    total_time = sum(s.get('tiempo', 0) for s in sessions)
    tipos = [s.get('tipo', '') for s in sessions]
    total_sessions = len(sessions)
    
    # Análisis de patrones para sugerencias más específicas
    grappling_count = sum(1 for tipo in tipos if 'grappling' in tipo.lower() or 'jiu' in tipo.lower() or 'bjj' in tipo.lower())
    striking_count = sum(1 for tipo in tipos if 'boxeo' in tipo.lower() or 'striking' in tipo.lower() or 'muay' in tipo.lower())
    conditioning_count = sum(1 for tipo in tipos if 'condicionamiento' in tipo.lower() or 'fuerza' in tipo.lower())
    
    # Sugerencias basadas en análisis de datos
    if total_sessions < 3:
        return "🔥 Buena base. Mantén la consistencia y ve incrementando gradualmente la intensidad."
    
    elif total_time > 300:  # Más de 5 horas semanales
        return "💪 Volumen excelente. Considera agregar un día de descanso activo con movilidad y recuperación."
    
    elif grappling_count > striking_count * 2:
        return "🥊 Balancea tu entrenamiento agregando más sesiones de striking para desarrollo completo en MMA."
    
    elif striking_count > grappling_count * 2:
        return "🤼 Enfócate en mejorar tu grappling. Agrega sesiones de BJJ o wrestling para equilibrio."
    
    elif conditioning_count == 0:
        return "🏋️ Agrega entrenamiento de fuerza y acondicionamiento para mejorar tu rendimiento general."
    
    else:
        # Sugerencias generales balanceadas
        fallback_suggestions = [
            "💡 Varía entre grappling y striking para desarrollo balanceado",
            "🔥 Mantén la consistencia y agrega días de descanso activo",
            "🥊 Enfócate en la técnica antes que la intensidad para prevenir lesiones",
            "💪 Incrementa gradualmente la duración de tus sesiones",
            "🔄 Incluye entrenamiento de movilidad para mejorar flexibilidad",
            "⏱️ Controla los tiempos de descanso entre rounds",
            "🏋️ Agrega ejercicios de fuerza funcional para mejorar tu poder",
            "🧘 No descuides el trabajo de flexibilidad y recuperación",
            "🎯 Trabaja transiciones entre striking y grappling",
            "💥 Incorpora sparring controlado para aplicar técnicas"
        ]
        return random.choice(fallback_suggestions)

# Ruta adicional para verificar estado de Gemini
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

