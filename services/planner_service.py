import json
import os
from datetime import datetime, date
from typing import List, Dict, Optional, Any

class PlannerService:
    def __init__(self, data_file: str = "data/sessions.json"):
        self.data_file = data_file
        self._ensure_data_file_exists()
    
    def _ensure_data_file_exists(self) -> None:
        """Crear el archivo de datos si no existe"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump([], f)
    
    def load_sessions(self) -> List[Dict[str, Any]]:
        """Cargar todas las sesiones desde el archivo JSON"""
        try:
            if os.path.getsize(self.data_file) == 0:
                return []
            
            with open(self.data_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)
                
            # Añadir ID a las sesiones si no lo tienen
            for i, session in enumerate(sessions):
                if 'id' not in session:
                    session['id'] = i
            
            # Ordenar por fecha (más recientes primero)
            sessions.sort(key=lambda x: x.get('fecha', ''), reverse=True)
            return sessions
            
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error al cargar sesiones: {e}")
            return []
    
    def save_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Guardar nueva sesión"""
        sessions = self.load_sessions()
        
        # Asignar ID único
        max_id = max([s.get('id', 0) for s in sessions], default=-1)
        session_data['id'] = max_id + 1
        
        # Añadir timestamp de creación
        session_data['created_at'] = datetime.now().isoformat()
        
        sessions.append(session_data)
        self._save_sessions(sessions)
        
        return session_data
    
    def update_session(self, session_id: int, updated_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Actualizar sesión existente"""
        sessions = self.load_sessions()
        
        for i, session in enumerate(sessions):
            if session.get('id') == session_id:
                # Mantener ID y timestamp original
                updated_data['id'] = session_id
                updated_data['created_at'] = session.get('created_at', datetime.now().isoformat())
                updated_data['updated_at'] = datetime.now().isoformat()
                
                sessions[i] = updated_data
                self._save_sessions(sessions)
                return updated_data
        
        return None
    
    def delete_session(self, session_id: int) -> bool:
        """Eliminar sesión por ID"""
        sessions = self.load_sessions()
        original_count = len(sessions)
        
        sessions = [s for s in sessions if s.get('id') != session_id]
        
        if len(sessions) < original_count:
            self._save_sessions(sessions)
            return True
        
        return False
    
    def _save_sessions(self, sessions: List[Dict[str, Any]]) -> None:
        """Guardar lista de sesiones al archivo"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise Exception(f"Error al guardar sesiones: {e}")
    
    def validate_session_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validar y procesar datos de sesión"""
        validated_data = {}
        
        # Validar fecha
        fecha = data.get('fecha', '').strip()
        if not fecha:
            raise ValueError("La fecha es requerida")
        
        try:
            # Verificar formato de fecha
            datetime.strptime(fecha, '%Y-%m-%d')
            validated_data['fecha'] = fecha
        except ValueError:
            raise ValueError("Formato de fecha inválido. Use YYYY-MM-DD")
        
        # Validar tipo de entrenamiento
        tipo = data.get('tipo', '').strip()
        valid_types = ['Cardio', 'Fuerza', 'Judo', 'MMA', 'Striking', 'Grappling', 'Técnico']
        
        if not tipo:
            raise ValueError("El tipo de entrenamiento es requerido")
        
        if tipo not in valid_types:
            raise ValueError(f"Tipo inválido. Tipos válidos: {', '.join(valid_types)}")
        
        validated_data['tipo'] = tipo
        
        # Validar tiempo
        try:
            tiempo = int(data.get('tiempo', 0))
            if tiempo <= 0:
                raise ValueError("El tiempo debe ser mayor a 0 minutos")
            if tiempo > 480:  # 8 horas máximo
                raise ValueError("El tiempo no puede exceder 480 minutos (8 horas)")
            validated_data['tiempo'] = tiempo
        except (ValueError, TypeError):
            raise ValueError("El tiempo debe ser un número entero válido")
        
        # Validar peso (opcional)
        peso = data.get('peso', 0)
        if peso:
            try:
                peso = float(peso)
                if peso < 30 or peso > 200:
                    raise ValueError("El peso debe estar entre 30 y 200 kg")
                validated_data['peso'] = peso
            except (ValueError, TypeError):
                raise ValueError("El peso debe ser un número válido")
        else:
            validated_data['peso'] = 0
        
        # Calcular calorías quemadas (estimación)
        validated_data['calorias'] = self._calculate_calories(
            validated_data['tipo'], 
            validated_data['tiempo'], 
            validated_data['peso']
        )
        
        # Campos opcionales
        validated_data['notas'] = data.get('notas', '').strip()[:500]  # Límite de 500 caracteres
        validated_data['intensidad'] = data.get('intensidad', 'Media')  # Baja, Media, Alta
        
        return validated_data
    
    def _calculate_calories(self, tipo: str, tiempo: int, peso: float) -> int:
        """Calcular calorías quemadas estimadas"""
        if peso <= 0:
            peso = 70  # Peso promedio por defecto
        
        # MET (Metabolic Equivalent of Task) por tipo de actividad
        met_values = {
            'Cardio': 8.0,
            'Fuerza': 6.0,
            'Judo': 10.0,
            'MMA': 12.0,
            'Striking': 9.0,
            'Grappling': 10.0,
            'Técnico': 4.0
        }
        
        met = met_values.get(tipo, 7.0)
        
        # Fórmula: Calorías = MET × peso(kg) × tiempo(horas)
        calories = met * peso * (tiempo / 60)
        
        return round(calories)
    
    def get_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Obtener sesión por ID"""
        sessions = self.load_sessions()
        for session in sessions:
            if session.get('id') == session_id:
                return session
        return None
    
    def search_sessions(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Buscar sesiones con filtros"""
        sessions = self.load_sessions()
        filtered_sessions = []
        
        for session in sessions:
            match = True
            
            # Filtro por tipo
            if query.get('tipo') and session.get('tipo') != query['tipo']:
                match = False
            
            # Filtro por rango de fechas
            if query.get('fecha_desde'):
                if session.get('fecha', '') < query['fecha_desde']:
                    match = False
            
            if query.get('fecha_hasta'):
                if session.get('fecha', '') > query['fecha_hasta']:
                    match = False
            
            # Filtro por duración mínima
            if query.get('tiempo_min'):
                if session.get('tiempo', 0) < query['tiempo_min']:
                    match = False
            
            if match:
                filtered_sessions.append(session)
        
        return filtered_sessions
