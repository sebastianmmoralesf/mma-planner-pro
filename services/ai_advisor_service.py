import os
import logging
from typing import List, Dict, Any
import requests

logger = logging.getLogger(__name__)

class AIAdvisorService:
    """Servicio para manejar consejos de IA con fallback elegante"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.is_configured = bool(self.api_key)
        
    def get_training_advice(self, sessions: List[Dict[str, Any]]) -> Dict[str, str]:
        """Obtener consejo de entrenamiento basado en sesiones"""
        
        if not sessions:
            return {
                "advice": "💡 Comienza agregando algunas sesiones de entrenamiento para recibir consejos personalizados.",
                "type": "info"
            }
        
        # Intentar con IA real si está configurada
        if self.is_configured:
            try:
                advice = self._get_gemini_advice(sessions)
                return {
                    "advice": advice,
                    "type": "ai"
                }
            except Exception as e:
                logger.warning(f"Fallo IA, usando fallback: {str(e)}")
        
        # Fallback inteligente basado en datos
        return {
            "advice": self._generate_fallback_advice(sessions),
            "type": "fallback"
        }
    
    def _get_gemini_advice(self, sessions: List[Dict[str, Any]]) -> str:
        """Obtener consejo de Gemini API"""
        if not self.is_configured:
            raise Exception("Gemini no configurado")
            
        prompt = self._build_prompt(sessions)
        
        # Tu código existente de Gemini aquí
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={self.api_key}"
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.8,
                "maxOutputTokens": 150
            }
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        advice = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        if not advice:
            raise Exception("Respuesta de IA vacía")
            
        return advice.strip()
    
    def _build_prompt(self, sessions: List[Dict[str, Any]]) -> str:
        """Construir prompt para la IA"""
        prompt = """Eres un entrenador experto de MMA. Analiza estas sesiones y da UN consejo específico y práctico.

Sesiones recientes:
"""
        
        for session in sessions[-8:]:  # Últimas 8 sesiones
            notes = f" - {session.get('notas')}" if session.get('notas') else ""
            prompt += f"- {session.get('fecha')}: {session.get('tipo')} ({session.get('tiempo')}min, {session.get('intensidad')}){notes}\n"
        
        prompt += "\nConsejo conciso (1-2 líneas, en español):"
        return prompt
    
    def _generate_fallback_advice(self, sessions: List[Dict[str, Any]]) -> str:
        """Generar consejo predefinido inteligente"""
        if len(sessions) < 2:
            return "💡 ¡Bien empezado! Agrega más sesiones para consejos personalizados."
        
        # Análisis básico de datos
        tipos = [s.get('tipo') for s in sessions]
        tiempo_promedio = sum(s.get('tiempo', 0) for s in sessions) / len(sessions)
        intensidades = [s.get('intensidad', 'Media') for s in sessions]
        
        # Lógica de consejos predefinidos
        if tiempo_promedio < 45:
            return "💡 Considera sesiones más largas (45-60min) para mejor desarrollo técnico."
        elif 'Grappling' not in tipos:
            return "💡 Incluye sesiones de grappling para mejorar tu juego en el suelo."
        elif 'Striking' not in tipos:
            return "💡 Agrega entrenamiento de striking para desarrollar tus golpes."
        elif all(i == 'Baja' for i in intensidades):
            return "💡 Incrementa gradualmente la intensidad para mejores ganancias."
        else:
            return "💡 Mantén la consistencia. Entrenar regularmente es clave en MMA."
