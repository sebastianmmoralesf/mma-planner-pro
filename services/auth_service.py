import hashlib
from typing import List, Dict, Any, Optional
import secrets
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class AuthService:
    def __init__(self, users_file: str = "data/users.json"):
        self.users_file = users_file
        self.tokens = {}  # En producción usar Redis o base de datos
        self._ensure_users_file_exists()
    
    def _ensure_users_file_exists(self) -> None:
        """Crear archivo de usuarios si no existe"""
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        
        if not os.path.exists(self.users_file):
            # Usuario por defecto para demo
            default_users = {
                "admin": {
                    "password_hash": self._hash_password("admin123"),
                    "created_at": datetime.now().isoformat(),
                    "role": "admin",
                    "email": "admin@mma-planner.com",
                    "full_name": "Administrador"
                },
                "demo": {
                    "password_hash": self._hash_password("demo123"),
                    "created_at": datetime.now().isoformat(),
                    "role": "user",
                    "email": "demo@mma-planner.com",
                    "full_name": "Usuario Demo"
                }
            }
            
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump(default_users, f, indent=2)
    
    def _load_users(self) -> Dict[str, Any]:
        """Cargar usuarios desde archivo"""
        try:
            with open(self.users_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_users(self, users: Dict[str, Any]) -> None:
        """Guardar usuarios en archivo"""
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    
    def _hash_password(self, password: str) -> str:
        """Hashear contraseña"""
        salt = "mma_training_salt_2024"  # En producción usar sal aleatoria por usuario
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def authenticate(self, username: str, password: str) -> bool:
        """Autenticar usuario"""
        users = self._load_users()
        
        if username not in users:
            return False
        
        password_hash = self._hash_password(password)
        return users[username]["password_hash"] == password_hash
    
    def generate_token(self, username: str) -> str:
        """Generar token de sesión"""
        token = secrets.token_urlsafe(32)
        
        self.tokens[token] = {
            "username": username,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=24)
        }
        
        return token
    
    def validate_token(self, token: str) -> Optional[str]:
        """Validar token y retornar username"""
        if token not in self.tokens:
            return None
        
        token_data = self.tokens[token]
        
        # Verificar expiración
        if datetime.now() > token_data["expires_at"]:
            del self.tokens[token]
            return None
        
        return token_data["username"]
    
    def create_user(self, username: str, password: str, email: str = "", full_name: str = "", role: str = "user") -> Dict[str, Any]:
        """Crear nuevo usuario"""
        users = self._load_users()
        
        # Validaciones
        if username in users:
            return {"success": False, "message": "El usuario ya existe"}
        
        if len(username) < 3:
            return {"success": False, "message": "El nombre de usuario debe tener al menos 3 caracteres"}
        
        if len(password) < 6:
            return {"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}
        
        # Validar email (básico)
        if email and "@" not in email:
            return {"success": False, "message": "Email inválido"}
        
        # Crear usuario
        users[username] = {
            "password_hash": self._hash_password(password),
            "created_at": datetime.now().isoformat(),
            "role": role,
            "email": email,
            "full_name": full_name or username.title(),
            "last_login": None,
            "login_count": 0
        }
        
        self._save_users(users)
        return {"success": True, "message": "Usuario creado exitosamente"}
    
    def change_password(self, username: str, old_password: str, new_password: str) -> Dict[str, Any]:
        """Cambiar contraseña de usuario"""
        if not self.authenticate(username, old_password):
            return {"success": False, "message": "Contraseña actual incorrecta"}
        
        if len(new_password) < 6:
            return {"success": False, "message": "La nueva contraseña debe tener al menos 6 caracteres"}
        
        users = self._load_users()
        users[username]["password_hash"] = self._hash_password(new_password)
        users[username]["password_changed_at"] = datetime.now().isoformat()
        
        self._save_users(users)
        
        # Invalidar todas las sesiones del usuario
        tokens_to_remove = [
            token for token, data in self.tokens.items()
            if data["username"] == username
        ]
        for token in tokens_to_remove:
            del self.tokens[token]
        
        return {"success": True, "message": "Contraseña cambiada exitosamente"}
    
    def logout(self, token: str) -> bool:
        """Cerrar sesión (invalidar token)"""
        if token in self.tokens:
            del self.tokens[token]
            return True
        return False
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Obtener información del usuario"""
        users = self._load_users()
        
        if username not in users:
            return None
        
        user_data = users[username].copy()
        # No retornar el hash de la contraseña
        user_data.pop("password_hash", None)
        user_data["username"] = username
        
        return user_data
    
    def update_login_stats(self, username: str) -> None:
        """Actualizar estadísticas de login"""
        users = self._load_users()
        
        if username in users:
            users[username]["last_login"] = datetime.now().isoformat()
            users[username]["login_count"] = users[username].get("login_count", 0) + 1
            self._save_users(users)
    
    def get_all_users(self, requesting_user: str) -> List[Dict[str, Any]]:
        """Obtener lista de todos los usuarios (solo para admins)"""
        users = self._load_users()
        
        # Verificar si el usuario solicitante es admin
        if requesting_user not in users or users[requesting_user].get("role") != "admin":
            return []
        
        user_list = []
        for username, data in users.items():
            user_info = data.copy()
            user_info.pop("password_hash", None)  # No incluir hash de contraseña
            user_info["username"] = username
            user_list.append(user_info)
        
        # Ordenar por fecha de creación (más recientes primero)
        user_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return user_list
    
    def delete_user(self, username_to_delete: str, requesting_user: str) -> Dict[str, Any]:
        """Eliminar usuario (solo para admins)"""
        users = self._load_users()
        
        # Verificar permisos
        if requesting_user not in users or users[requesting_user].get("role") != "admin":
            return {"success": False, "message": "Sin permisos para eliminar usuarios"}
        
        # No permitir auto-eliminación
        if username_to_delete == requesting_user:
            return {"success": False, "message": "No puedes eliminar tu propia cuenta"}
        
        # Verificar si el usuario existe
        if username_to_delete not in users:
            return {"success": False, "message": "Usuario no encontrado"}
        
        # Eliminar usuario
        del users[username_to_delete]
        self._save_users(users)
        
        # Invalidar todas las sesiones del usuario eliminado
        tokens_to_remove = [
            token for token, data in self.tokens.items()
            if data["username"] == username_to_delete
        ]
        for token in tokens_to_remove:
            del self.tokens[token]
        
        return {"success": True, "message": f"Usuario {username_to_delete} eliminado exitosamente"}
    
    def update_user_role(self, username: str, new_role: str, requesting_user: str) -> Dict[str, Any]:
        """Cambiar rol de usuario (solo para admins)"""
        users = self._load_users()
        
        # Verificar permisos
        if requesting_user not in users or users[requesting_user].get("role") != "admin":
            return {"success": False, "message": "Sin permisos para cambiar roles"}
        
        # Verificar si el usuario existe
        if username not in users:
            return {"success": False, "message": "Usuario no encontrado"}
        
        # Validar nuevo rol
        valid_roles = ["user", "admin", "moderator"]
        if new_role not in valid_roles:
            return {"success": False, "message": f"Rol inválido. Roles válidos: {', '.join(valid_roles)}"}
        
        # No permitir cambiar el propio rol
        if username == requesting_user:
            return {"success": False, "message": "No puedes cambiar tu propio rol"}
        
        # Actualizar rol
        old_role = users[username].get("role", "user")
        users[username]["role"] = new_role
        users[username]["role_changed_at"] = datetime.now().isoformat()
        users[username]["role_changed_by"] = requesting_user
        
        self._save_users(users)
        
        return {
            "success": True, 
            "message": f"Rol de {username} cambiado de {old_role} a {new_role}"
        }
    
    def cleanup_expired_tokens(self) -> int:
        """Limpiar tokens expirados y retornar cantidad eliminada"""
        now = datetime.now()
        expired_tokens = [
            token for token, data in self.tokens.items()
            if now > data["expires_at"]
        ]
        
        for token in expired_tokens:
            del self.tokens[token]
        
        return len(expired_tokens)
    
    def get_active_sessions_count(self) -> int:
        """Obtener número de sesiones activas"""
        self.cleanup_expired_tokens()  # Limpiar primero
        return len(self.tokens)
    
    def get_user_sessions(self, username: str) -> List[Dict[str, Any]]:
        """Obtener sesiones activas de un usuario específico"""
        user_sessions = []
        
        for token, data in self.tokens.items():
            if data["username"] == username:
                user_sessions.append({
                    "token": token[:8] + "...",  # Solo mostrar parte del token por seguridad
                    "created_at": data["created_at"].isoformat(),
                    "expires_at": data["expires_at"].isoformat(),
                    "time_remaining": str(data["expires_at"] - datetime.now()).split('.')[0]
                })
        
        return user_sessions
    
    def extend_token(self, token: str, hours: int = 24) -> bool:
        """Extender duración de un token"""
        if token not in self.tokens:
            return False
        
        self.tokens[token]["expires_at"] = datetime.now() + timedelta(hours=hours)
        return True
    
    def get_auth_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas generales de autenticación"""
        users = self._load_users()
        
        # Contar usuarios por rol
        role_counts = {}
        total_logins = 0
        users_with_logins = 0
        
        for username, data in users.items():
            role = data.get("role", "user")
            role_counts[role] = role_counts.get(role, 0) + 1
            
            login_count = data.get("login_count", 0)
            total_logins += login_count
            if login_count > 0:
                users_with_logins += 1
        
        return {
            "total_users": len(users),
            "active_sessions": self.get_active_sessions_count(),
            "role_distribution": role_counts,
            "total_logins": total_logins,
            "users_with_activity": users_with_logins,
            "avg_logins_per_user": round(total_logins / len(users), 1) if users else 0
        }