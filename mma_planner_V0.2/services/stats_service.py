from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict
import calendar

class StatsService:
    def __init__(self):
        pass
    
    def calculate_comprehensive_stats(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcular estadísticas completas para el frontend"""
        if not sessions:
            return self._empty_stats()
        
        total_sessions = len(sessions)
        total_time = sum(session.get('tiempo', 0) for session in sessions)
        total_calories = sum(session.get('calorias', 0) for session in sessions)
        
        # Estadísticas básicas
        stats = {
            'total_sessions': total_sessions,
            'total_time': total_time,
            'total_time_hours': round(total_time / 60, 1),
            'total_calories': total_calories,
            'avg_session_time': round(total_time / total_sessions, 1) if total_sessions > 0 else 0,
            'avg_calories_per_session': round(total_calories / total_sessions) if total_sessions > 0 else 0
        }
        
        # Tipo más frecuente
        type_counts = defaultdict(int)
        for session in sessions:
            type_counts[session.get('tipo', 'Desconocido')] += 1
        
        if type_counts:
            stats['most_frequent_type'] = max(type_counts, key=type_counts.get)
            stats['most_frequent_count'] = type_counts[stats['most_frequent_type']]
        else:
            stats['most_frequent_type'] = 'N/A'
            stats['most_frequent_count'] = 0
        
        # Estadísticas por tipo
        stats['by_type'] = self.calculate_stats_by_type(sessions)
        
        # Estadísticas temporales
        stats['recent_activity'] = self._calculate_recent_activity(sessions)
        stats['weekly_average'] = self._calculate_weekly_average(sessions)
        stats['monthly_totals'] = self.calculate_monthly_stats(sessions)
        
        # Streaks y patrones
        stats['current_streak'] = self._calculate_current_streak(sessions)
        stats['longest_streak'] = self._calculate_longest_streak(sessions)
        
        # Estadísticas de intensidad
        stats['intensity_distribution'] = self._calculate_intensity_stats(sessions)
        
        return stats
    
    def calculate_stats_by_type(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calcular estadísticas por tipo de entrenamiento"""
        if not sessions:
            return []
            
        type_stats = defaultdict(lambda: {
            'sessions': 0,
            'total_time': 0,
            'total_calories': 0,
            'avg_time': 0,
            'avg_calories': 0
        })
        
        for session in sessions:
            tipo = session.get('tipo', 'Desconocido')
            type_stats[tipo]['sessions'] += 1
            type_stats[tipo]['total_time'] += session.get('tiempo', 0)
            type_stats[tipo]['total_calories'] += session.get('calorias', 0)
        
        # Calcular promedios y crear lista de resultados
        result = []
        for tipo, stats in type_stats.items():
            if stats['sessions'] > 0:
                stats['avg_time'] = round(stats['total_time'] / stats['sessions'], 1)
                stats['avg_calories'] = round(stats['total_calories'] / stats['sessions'])
            
            result.append({
                'tipo': tipo,
                'sessions': stats['sessions'],
                'total_time': stats['total_time'],
                'total_calories': stats['total_calories'],
                'avg_time': stats['avg_time'],
                'avg_calories': stats['avg_calories'],
                'percentage': round((stats['sessions'] / len(sessions)) * 100, 1) if sessions else 0
            })
        
        # Ordenar por número de sesiones (descendente)
        result.sort(key=lambda x: x['sessions'], reverse=True)
        return result
    
    def calculate_monthly_stats(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calcular estadísticas mensuales"""
        if not sessions:
            return []
            
        monthly_stats = defaultdict(lambda: {
            'sessions': 0,
            'total_time': 0,
            'total_calories': 0,
            'types': defaultdict(int),
            'avg_session_time': 0
        })
        
        for session in sessions:
            fecha = session.get('fecha', '')
            if not fecha:
                continue
            
            try:
                date_obj = datetime.strptime(fecha, '%Y-%m-%d')
                month_key = f"{date_obj.year}-{date_obj.month:02d}"
                month_name = f"{calendar.month_name[date_obj.month]} {date_obj.year}"
                
                monthly_stats[month_key]['month_name'] = month_name
                monthly_stats[month_key]['year'] = date_obj.year
                monthly_stats[month_key]['month_number'] = date_obj.month
                monthly_stats[month_key]['sessions'] += 1
                monthly_stats[month_key]['total_time'] += session.get('tiempo', 0)
                monthly_stats[month_key]['total_calories'] += session.get('calorias', 0)
                monthly_stats[month_key]['types'][session.get('tipo', 'Desconocido')] += 1
                
            except ValueError:
                continue
        
        # Convertir a lista y calcular promedios
        result = []
        for month_key, stats in monthly_stats.items():
            stats['month'] = month_key
            stats['avg_session_time'] = round(stats['total_time'] / stats['sessions'], 1) if stats['sessions'] > 0 else 0
            
            # Tipo más común del mes
            if stats['types']:
                most_common_type = max(stats['types'], key=stats['types'].get)
                stats['most_common_type'] = most_common_type
            else:
                stats['most_common_type'] = 'N/A'
            
            # Calcular días promedio por mes (asumiendo 30 días)
            stats['sessions_per_week'] = round((stats['sessions'] / 30) * 7, 1) if stats['sessions'] > 0 else 0
            
            result.append(stats)
        
        # Ordenar por fecha (más recientes primero)
        result.sort(key=lambda x: x['month'], reverse=True)
        return result
    
    def _calculate_recent_activity(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcular actividad reciente (últimos 7 y 30 días)"""
        now = datetime.now().date()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)
        
        recent_7_sessions = []
        recent_30_sessions = []
        
        for session in sessions:
            fecha = session.get('fecha', '')
            if not fecha:
                continue
            
            try:
                session_date = datetime.strptime(fecha, '%Y-%m-%d').date()
                
                if session_date >= last_7_days:
                    recent_7_sessions.append(session)
                
                if session_date >= last_30_days:
                    recent_30_sessions.append(session)
                    
            except ValueError:
                continue
        
        return {
            'last_7_days': {
                'sessions': len(recent_7_sessions),
                'total_time': sum(s.get('tiempo', 0) for s in recent_7_sessions),
                'total_calories': sum(s.get('calorias', 0) for s in recent_7_sessions),
                'avg_per_day': round(len(recent_7_sessions) / 7, 1)
            },
            'last_30_days': {
                'sessions': len(recent_30_sessions),
                'total_time': sum(s.get('tiempo', 0) for s in recent_30_sessions),
                'total_calories': sum(s.get('calorias', 0) for s in recent_30_sessions),
                'avg_per_day': round(len(recent_30_sessions) / 30, 1)
            }
        }
    
    def _calculate_weekly_average(self, sessions: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calcular promedios semanales"""
        if not sessions:
            return {'sessions': 0, 'time': 0, 'calories': 0}
        
        # Obtener rango de fechas válidas
        valid_dates = []
        for session in sessions:
            fecha = session.get('fecha', '')
            if fecha:
                try:
                    valid_dates.append(datetime.strptime(fecha, '%Y-%m-%d').date())
                except ValueError:
                    continue
        
        if not valid_dates:
            return {'sessions': 0, 'time': 0, 'calories': 0}
        
        # Calcular número de semanas en el rango de datos
        min_date = min(valid_dates)
        max_date = max(valid_dates)
        total_days = (max_date - min_date).days + 1
        weeks = max(total_days / 7, 1)  # Mínimo 1 semana
        
        total_time = sum(session.get('tiempo', 0) for session in sessions)
        total_calories = sum(session.get('calorias', 0) for session in sessions)
        
        return {
            'sessions': round(len(sessions) / weeks, 1),
            'time': round(total_time / weeks, 1),
            'calories': round(total_calories / weeks),
            'weeks_analyzed': round(weeks, 1)
        }
    
    def _calculate_current_streak(self, sessions: List[Dict[str, Any]]) -> int:
        """Calcular racha actual de días consecutivos con entrenamiento"""
        if not sessions:
            return 0
        
        # Obtener fechas únicas y ordenarlas
        unique_dates = set()
        for session in sessions:
            fecha = session.get('fecha', '')
            if fecha:
                try:
                    unique_dates.add(datetime.strptime(fecha, '%Y-%m-%d').date())
                except ValueError:
                    continue
        
        if not unique_dates:
            return 0
        
        sorted_dates = sorted(unique_dates, reverse=True)
        current_date = datetime.now().date()
        
        # Verificar si hay entrenamiento hoy o ayer (para mantener racha)
        if sorted_dates[0] not in [current_date, current_date - timedelta(days=1)]:
            return 0
        
        # Contar días consecutivos hacia atrás
        streak = 0
        expected_date = sorted_dates[0]
        
        for date in sorted_dates:
            if date == expected_date:
                streak += 1
                expected_date = date - timedelta(days=1)
            else:
                break
        
        return streak
    
    def _calculate_longest_streak(self, sessions: List[Dict[str, Any]]) -> int:
        """Calcular la racha más larga de días consecutivos en la historia"""
        if not sessions:
            return 0
        
        # Obtener fechas únicas y ordenarlas
        unique_dates = set()
        for session in sessions:
            fecha = session.get('fecha', '')
            if fecha:
                try:
                    unique_dates.add(datetime.strptime(fecha, '%Y-%m-%d').date())
                except ValueError:
                    continue
        
        if not unique_dates:
            return 0
        
        sorted_dates = sorted(unique_dates)
        
        if len(sorted_dates) == 1:
            return 1
        
        max_streak = 1
        current_streak = 1
        
        # Buscar la secuencia más larga de días consecutivos
        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == sorted_dates[i-1] + timedelta(days=1):
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        return max_streak
    
    def _calculate_intensity_stats(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcular estadísticas de distribución por intensidad"""
        intensity_counts = defaultdict(int)
        intensity_time = defaultdict(int)
        intensity_calories = defaultdict(int)
        
        for session in sessions:
            intensity = session.get('intensidad', 'Media')
            intensity_counts[intensity] += 1
            intensity_time[intensity] += session.get('tiempo', 0)
            intensity_calories[intensity] += session.get('calorias', 0)
        
        total_sessions = sum(intensity_counts.values())
        total_time = sum(intensity_time.values())
        
        result = {}
        for intensity in ['Baja', 'Media', 'Alta']:
            count = intensity_counts.get(intensity, 0)
            time = intensity_time.get(intensity, 0)
            calories = intensity_calories.get(intensity, 0)
            
            result[intensity] = {
                'count': count,
                'percentage': round((count / total_sessions) * 100, 1) if total_sessions > 0 else 0,
                'total_time': time,
                'time_percentage': round((time / total_time) * 100, 1) if total_time > 0 else 0,
                'total_calories': calories,
                'avg_time': round(time / count, 1) if count > 0 else 0
            }
        
        return result
    
    def get_performance_trends(self, sessions: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
        """Calcular tendencias de rendimiento en los últimos N días"""
        if not sessions:
            return {'trend': 'stable', 'change_percentage': 0}
        
        cutoff_date = datetime.now().date() - timedelta(days=days)
        recent_sessions = []
        
        for session in sessions:
            fecha = session.get('fecha', '')
            if fecha:
                try:
                    session_date = datetime.strptime(fecha, '%Y-%m-%d').date()
                    if session_date >= cutoff_date:
                        recent_sessions.append(session)
                except ValueError:
                    continue
        
        if len(recent_sessions) < 4:  # Necesitamos datos suficientes
            return {'trend': 'insufficient_data', 'change_percentage': 0}
        
        # Dividir en dos períodos para comparar
        mid_point = len(recent_sessions) // 2
        first_half = recent_sessions[:mid_point]
        second_half = recent_sessions[mid_point:]
        
        avg_time_first = sum(s.get('tiempo', 0) for s in first_half) / len(first_half)
        avg_time_second = sum(s.get('tiempo', 0) for s in second_half) / len(second_half)
        
        if avg_time_first == 0:
            return {'trend': 'stable', 'change_percentage': 0}
        
        change_percentage = ((avg_time_second - avg_time_first) / avg_time_first) * 100
        
        if change_percentage > 10:
            trend = 'improving'
        elif change_percentage < -10:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'change_percentage': round(change_percentage, 1),
            'avg_time_first_period': round(avg_time_first, 1),
            'avg_time_second_period': round(avg_time_second, 1)
        }
    
    def _empty_stats(self) -> Dict[str, Any]:
        """Retornar estadísticas vacías cuando no hay sesiones"""
        return {
            'total_sessions': 0,
            'total_time': 0,
            'total_time_hours': 0,
            'total_calories': 0,
            'avg_session_time': 0,
            'avg_calories_per_session': 0,
            'most_frequent_type': 'N/A',
            'most_frequent_count': 0,
            'by_type': [],
            'recent_activity': {
                'last_7_days': {'sessions': 0, 'total_time': 0, 'total_calories': 0, 'avg_per_day': 0},
                'last_30_days': {'sessions': 0, 'total_time': 0, 'total_calories': 0, 'avg_per_day': 0}
            },
            'weekly_average': {'sessions': 0, 'time': 0, 'calories': 0, 'weeks_analyzed': 0},
            'monthly_totals': [],
            'current_streak': 0,
            'longest_streak': 0,
            'intensity_distribution': {
                'Baja': {'count': 0, 'percentage': 0, 'total_time': 0, 'time_percentage': 0, 'total_calories': 0, 'avg_time': 0},
                'Media': {'count': 0, 'percentage': 0, 'total_time': 0, 'time_percentage': 0, 'total_calories': 0, 'avg_time': 0},
                'Alta': {'count': 0, 'percentage': 0, 'total_time': 0, 'time_percentage': 0, 'total_calories': 0, 'avg_time': 0}
            }
        }
