from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import logging
from functools import wraps
import requests
import random

# --- Inicio del Mock de Servicios (para que el código sea ejecutable por sí solo) ---
class MockService:
    def __init__(self):
        self._sessions = {
            1: {'id': 1, 'fecha': '2024-10-01', 'tipo': 'Grappling', 'tiempo': 90, 'intensidad': 'Alta', 'notas': 'Técnica de sumisión'},
            2: {'id': 2, 'fecha': '2024-10-02', 'tipo': 'Boxeo', 'tiempo': 60, 'intensidad': 'Media', 'notas': 'Trabajo de pies'},
        }
        self._next_id = 3
    
    def validate_session_data(self, data): 
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
        total_time = sum(s.get('tiempo', 0) for s in sessions)
        return {
            "total_sessions": len(sessions),
            "total_time": total_time,
            "total_time_hours": round(total_time / 60, 1),
            "total_calories": sum(s.get('calorias', 0) for s in sessions),
            "avg_session_time": round(total_time / len(sessions), 1) if sessions else 0,
            "most_frequent_type": "MMA",
            "current_streak": 3,
            "longest_streak": 7,
            "recent_activity": {
                "last_7_days": {"sessions": 3, "total_time": 180},
                "last_30_days": {"sessions": 10, "total_time": 600}
            },
            "weekly_average": {"sessions": 3, "time": 180}
        }
    
    def calculate_stats_by_type(self, sessions): 
        return [
            {"tipo": "MMA", "sessions": 5, "percentage": 50, "total_time": 300, "avg_time": 60, "total_calories": 1500},
            {"tipo": "Cardio", "sessions": 3, "percentage": 30, "total_time": 150, "avg_time": 50, "total_calories": 900}
        ]
    
    def calculate_monthly_stats(self, sessions): 
        return [
            {"month_name": "Octubre 2024", "sessions": 10, "total_time": 600, "avg_session_time": 60, "most_common_type": "MMA"}
        ]
    
    def export_to_csv(self, sessions): 
        path = os.path.join("exports", "data.csv")
        os.makedirs("exports", exist_ok=True)
        open(path, "w").close()
        return path
    
    def export_to_excel(self, sessions): 
        path = os.path.join("exports", "data.xlsx")
        os.makedirs("exports", exist_ok=True)
        open(path, "w").close()
        return path
    
    def export_to_pdf(self, sessions, stats): 
        path = os.path.join("exports", "data.pdf")
        os.makedirs("exports", exist_ok=True)
        open(path, "w").close()
        return path
    
    def authenticate(self, u, p): 
        return True
    
    def generate_token(self, u): 
        return "fake-token"

planner_service = MockService()
export_service = MockService()
stats_service = MockService()
auth_service = MockService()
# --- Fin del Mock de Servicios ---

app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAdvisorService:
    """Servicio mejorado para consejos de entrenamiento con IA"""
    
    def __init__(self):
        self.gemini_manager = GeminiManager()
    
    def get_training_advice(self, sessions):
        """Obtener consejo de entrenamiento"""
        if not sessions:
            return {
                "advice": "💡 Comienza agregando algunas sesiones de entrenamiento para recibir consejos personalizados.",
                "type": "info"
            }
        
        try:
            if self.gemini_manager.is_configured:
                prompt = self._build_advanced_prompt(sessions)
                advice = self.gemini_manager.get_suggestion(prompt)
                return {"advice": advice, "type": "ai"}
            else:
                advice = self._generate_smart_fallback(sessions)
                return {"advice": advice, "type": "fallback"}
        except Exception as e:
            logger.error(f"Error en AI Advisor: {str(e)}")
            advice = self._generate_smart_fallback(sessions)
            return {"advice": advice, "type": "fallback"}
    
    def _build_advanced_prompt(self, sessions):
        """Construir prompt detallado para la IA"""
        # Análisis de datos
        total_sessions = len(sessions)
        tipos = [s.get('tipo') for s in sessions]
        intensidades = [s.get('intensidad', 'Media') for s in sessions]
        tiempo_total = sum(s.get('tiempo', 0) for s in sessions)
        
        # Contar frecuencias
        tipo_counts = {}
        for tipo in tipos:
            tipo_counts[tipo] = tipo_counts.get(tipo, 0) + 1
        
        intensidad_counts = {}
        for intensidad in intensidades:
            intensidad_counts[intensidad] = intensidad_counts.get(intensidad, 0) + 1
        
        prompt = f"""Eres un entrenador experto de MMA con 15 años de experiencia. Analiza estos datos de entrenamiento y da UN consejo específico y accionable.

📊 DATOS DEL ATLETA:
- Total de sesiones: {total_sessions}
- Tiempo total entrenado: {tiempo_total} minutos ({tiempo_total/60:.1f} horas)
- Promedio por sesión: {tiempo_total/total_sessions:.0f} minutos

🥊 DISTRIBUCIÓN POR TIPO:
{chr(10).join([f'- {tipo}: {count} sesiones ({count/total_sessions*100:.0f}%)' for tipo, count in tipo_counts.items()])}

🔥 DISTRIBUCIÓN DE INTENSIDAD:
{chr(10).join([f'- {intensidad}: {count} sesiones' for intensidad, count in intensidad_counts.items()])}

📅 ÚLTIMAS 5 SESIONES:
{chr(10).join([f'- {s.get("fecha")}: {s.get("tipo")} - {s.get("tiempo")}min - {s.get("intensidad", "Media")}' for s in sessions[-5:]])}

Da UN consejo práctico y específico basado en estos datos (máximo 2 líneas). Enfócate en:
1. Balance entre tipos de entrenamiento
2. Intensidad apropiada
3. Progresión y recuperación
4. Áreas de mejora específicas

Consejo:"""
        
        return prompt
    
    def _generate_smart_fallback(self, sessions):
        """Generar consejos inteligentes basados en análisis de datos"""
        if len(sessions) < 3:
            return "💡 Agrega más sesiones para recibir análisis detallados. La consistencia es clave en MMA."
        
        # Análisis de datos
        tipos = [s.get('tipo') for s in sessions]
        intensidades = [s.get('intensidad', 'Media') for s in sessions]
        tiempos = [s.get('tiempo', 0) for s in sessions]
        
        tiempo_total = sum(tiempos)
        tiempo_promedio = tiempo_total / len(sessions)
        
        # Contar tipos
        tipo_counts = {}
        for tipo in tipos:
            tipo_counts[tipo] = tipo_counts.get(tipo, 0) + 1
        
        # Contar intensidades
        intensidad_counts = {}
        for intensidad in intensidades:
            intensidad_counts[intensidad] = intensidad_counts.get(intensidad, 0) + 1
        
        # Consejos basados en análisis
        consejos = []
        
        # 1. Análisis de balance
        if len(tipo_counts) == 1:
            consejos.append("💡 Diversifica tu entrenamiento. Incluye diferentes disciplinas (striking, grappling, cardio) para un desarrollo completo.")
        
        # 2. Análisis de intensidad
        alta_intensidad = intensidad_counts.get('Alta', 0)
        if alta_intensidad > len(sessions) * 0.7:
            consejos.append("⚠️ Más del 70% de tus entrenamientos son de alta intensidad. Incluye sesiones de recuperación activa para evitar sobreentrenamiento.")
        elif alta_intensidad == 0 and len(sessions) > 5:
            consejos.append("🔥 Considera agregar sesiones de alta intensidad para mejorar tu capacidad anaeróbica y potencia.")
        
        # 3. Análisis de tiempo
        if tiempo_promedio < 45:
            consejos.append("⏱️ Tus sesiones promedian menos de 45 min. Aumenta gradualmente la duración para mejorar resistencia.")
        elif tiempo_promedio > 120:
            consejos.append("💪 Sesiones largas detectadas. Asegúrate de mantener la calidad sobre la cantidad y recuperarte adecuadamente.")
        
        # 4. Análisis de tipos específicos
        if 'Cardio' not in tipos and len(sessions) > 5:
            consejos.append("🏃 Agrega sesiones de cardio dedicadas para mejorar tu condición aeróbica base.")
        
        if 'Grappling' not in tipos and 'Striking' not in tipos:
            consejos.append("🥋 Incluye entrenamiento específico de grappling y striking para un desarrollo MMA completo.")
        
        # 5. Análisis de consistencia (últimas sesiones)
        fechas_recientes = [s.get('fecha') for s in sessions[-7:]]
        if len(fechas_recientes) < 3:
            consejos.append("📅 Trata de entrenar al menos 3 veces por semana para mantener progreso constante.")
        
        # Si no hay consejos específicos, dar uno general positivo
        if not consejos:
            consejos.append("✅ Excelente balance en tu entrenamiento. Continúa así y enfócate en la técnica y la progresión gradual.")
        
        # Retornar un consejo aleatorio de los generados
        return random.choice(consejos)


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
            logger.warning("⚠️ GEMINI_API_KEY no encontrada. Usando sistema de fallback.")
            self.is_configured = False
        else:
            self.is_configured = True
            logger.info("✅ Gemini API configurada correctamente.")

    def get_suggestion(self, prompt):
        """Obtener sugerencia de Gemini a través de la API REST"""
        if not self.is_configured:
            raise Exception("Gemini no está configurado.")

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 200
            }
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            suggestion = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            if not suggestion:
                raise Exception("Respuesta vacía de Gemini.")
            
            return suggestion.strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en API Gemini: {e}")
            raise Exception(f"Error de conexión con IA: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"Error al parsear respuesta Gemini: {e}")
            raise Exception("Formato de respuesta inesperado.")


# Inicializar servicios
ai_advisor = AIAdvisorService()


def validate_json(required_fields=None):
    """Decorador para validar JSON"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({"status": "error", "message": "Content-Type debe ser application/json"}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "JSON vacío o inválido"}), 400
            
            if required_fields:
                missing = [field for field in required_fields if field not in data or data[field] is None]
                if missing:
                    return jsonify({"status": "error", "message": f"Campos requeridos faltantes: {', '.join(missing)}"}), 400
            
            return f(data, *args, **kwargs)
        return decorated_function
    return decorator


def handle_errors(f):
    """Decorador para manejo de errores"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error interno: {str(e)}")
            return jsonify({"status": "error", "message": "Error interno del servidor"}), 500
    return decorated_function


# ==================== RUTAS ====================

@app.route("/", methods=["GET"])
def home():
    """Ruta de inicio"""
    return jsonify({
        "app": "MMA Training Planner Pro API",
        "version": "2.0",
        "status": "running"
    })


@app.route("/api/health", methods=["GET"])
def health_check():
    """Verificar estado del servicio"""
    return jsonify({
        "status": "ok",
        "gemini_ai": "configured" if ai_advisor.gemini_manager.is_configured else "not_configured",
        "fallback_system": "active"
    })


@app.route("/api/sessions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def add_session(data):
    """Agregar nueva sesión de entrenamiento"""
    session = planner_service.save_session(data)
    return jsonify({"status": "success", "data": session}), 201


@app.route("/api/sessions", methods=["GET"])
@handle_errors
def get_sessions():
    """Obtener todas las sesiones"""
    sessions = planner_service.load_sessions()
    return jsonify({"status": "success", "data": sessions})


@app.route("/api/sessions/<int:session_id>", methods=["PUT"])
@handle_errors
@validate_json(required_fields=["fecha", "tipo", "tiempo"])
def update_session(data, session_id):
    """Actualizar sesión existente"""
    session = planner_service.update_session(session_id, data)
    if session:
        return jsonify({"status": "success", "data": session})
    return jsonify({"status": "error", "message": "Sesión no encontrada"}), 404


@app.route("/api/sessions/<int:session_id>", methods=["DELETE"])
@handle_errors
def delete_session(session_id):
    """Eliminar sesión"""
    success = planner_service.delete_session(session_id)
    if success:
        return jsonify({"status": "success", "message": "Sesión eliminada"})
    return jsonify({"status": "error", "message": "Sesión no encontrada"}), 404


@app.route("/api/stats/summary", methods=["GET"])
@handle_errors
def get_stats_summary():
    """Obtener estadísticas resumidas"""
    sessions = planner_service.load_sessions()
    stats = stats_service.calculate_comprehensive_stats(sessions)
    return jsonify({"status": "success", "data": stats})


@app.route("/api/stats/by-type", methods=["GET"])
@handle_errors
def get_stats_by_type():
    """Obtener estadísticas por tipo de entrenamiento"""
    sessions = planner_service.load_sessions()
    stats = stats_service.calculate_stats_by_type(sessions)
    return jsonify({"status": "success", "data": stats})


@app.route("/api/stats/monthly", methods=["GET"])
@handle_errors
def get_monthly_stats():
    """Obtener estadísticas mensuales"""
    sessions = planner_service.load_sessions()
    stats = stats_service.calculate_monthly_stats(sessions)
    return jsonify({"status": "success", "data": stats})


@app.route("/api/export/<format>", methods=["GET"])
@handle_errors
def export_data(format):
    """Exportar datos en diferentes formatos"""
    sessions = planner_service.load_sessions()
    
    if format == "csv":
        filepath = export_service.export_to_csv(sessions)
    elif format == "excel":
        filepath = export_service.export_to_excel(sessions)
    elif format == "pdf":
        stats = stats_service.calculate_comprehensive_stats(sessions)
        filepath = export_service.export_to_pdf(sessions, stats)
    else:
        return jsonify({"status": "error", "message": "Formato no soportado"}), 400
    
    return send_file(filepath, as_attachment=True)


@app.route("/api/ai-advice", methods=["POST"])
@handle_errors
@validate_json(required_fields=["sessions"])
def get_ai_advice(data):
    """
    Obtener consejos de IA basados en las sesiones de entrenamiento
    Endpoint principal para el Asistente IA
    """
    sessions = data.get("sessions", [])
    
    # Obtener consejo del servicio de IA
    result = ai_advisor.get_training_advice(sessions)
    
    return jsonify({
        "status": "success",
        "advice": result["advice"],
        "type": result["type"]
    })


@app.route("/api/ai-suggestions", methods=["POST"])
@handle_errors
@validate_json(required_fields=["sessions"])
def ai_suggestions(data):
    """
    Endpoint legacy para sugerencias de IA
    (mantener por compatibilidad)
    """
    sessions = data.get("sessions", [])
    result = ai_advisor.get_training_advice(sessions)
    
    return jsonify({
        "status": "success",
        "sugerencia": result["advice"],
        "tipo": result["type"]
    })


# ==================== MAIN ====================

if __name__ == "__main__":
    # Crear carpeta de exportaciones
    os.makedirs("exports", exist_ok=True)
    
    # Obtener puerto
    port = int(os.environ.get("PORT", 5000))
    
    # Mensaje de inicio
    logger.info("=" * 50)
    logger.info("🥋 MMA Training Planner Pro API")
    logger.info("=" * 50)
    logger.info(f"🚀 Servidor iniciando en puerto {port}")
    logger.info(f"🤖 IA Status: {'Configurada' if ai_advisor.gemini_manager.is_configured else 'Modo Fallback'}")
    logger.info("=" * 50)
    
    # Iniciar servidor
    app.run(debug=False, host="0.0.0.0", port=port)
