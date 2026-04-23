"""
cache.py — Sistema de caché para el analizador

¿Por qué existe este módulo?
Si analizas el mismo proyecto dos veces, no tiene sentido volver a
mandarle a Claude los archivos que no cambiaron. Este módulo:
  1. Calcula un "huella digital" (MD5) de cada archivo
  2. Si el archivo no cambió, devuelve el resultado anterior
  3. Si cambió, deja que el agente lo procese de nuevo

Conceptos de Python que verás aquí:
  - hashlib: librería built-in para calcular hashes
  - json: leer y escribir JSON desde Python
  - dataclass: forma moderna de definir clases de datos simples
  - Optional[tipo]: indica que un valor puede ser None
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Optional


# Ruta donde se guarda el archivo de caché
CACHE_FILE = ".analizador_cache.json"


def _calcular_hash(path: str) -> str:
    """
    Calcula el hash MD5 del contenido de un archivo.
    
    MD5 genera una cadena de 32 caracteres que cambia si el archivo cambia.
    Es como una huella digital del contenido.
    
    El prefijo _ indica que es una función interna del módulo
    (convención de Python, equivale a "private" en Java).
    """
    hasher = hashlib.md5()
    
    # Abrimos en modo binario ("rb") para no tener problemas con encodings
    with open(path, "rb") as f:
        # read() en chunks de 8KB — eficiente para archivos grandes
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    
    return hasher.hexdigest()  # Regresa el hash como string hexadecimal


def _cargar_cache() -> dict:
    """Carga el archivo de caché. Si no existe, regresa un dict vacío."""
    if not os.path.exists(CACHE_FILE):
        return {}
    
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}  # Si el archivo está corrupto, empezamos de cero


def _guardar_cache(cache: dict) -> None:
    """Guarda el diccionario de caché en disco."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        # indent=2 hace el JSON legible para humanos
        json.dump(cache, f, indent=2, ensure_ascii=False)


def obtener_cache(path: str) -> Optional[str]:
    """
    Revisa si tenemos un resultado cacheado para este archivo.
    
    Returns:
        El resultado cacheado si el archivo no cambió, o None si cambió.
    
    Optional[str] significa: puede regresar un str o puede regresar None.
    Equivale a String | null en Java moderno.
    """
    if not os.path.exists(path):
        return None
    
    cache = _cargar_cache()
    hash_actual = _calcular_hash(path)
    
    entrada = cache.get(path)  # .get() regresa None si la clave no existe
    
    if entrada and entrada.get("hash") == hash_actual:
        return entrada.get("resultado")
    
    return None  # Archivo cambió o no estaba en caché


def guardar_en_cache(path: str, resultado: str) -> None:
    """
    Guarda el resultado del análisis de un archivo en el caché.
    
    Guardamos:
    - hash: para saber si el archivo cambió
    - resultado: el análisis que hizo la IA
    - timestamp: cuándo se analizó (informativo)
    """
    cache = _cargar_cache()
    
    cache[path] = {
        "hash": _calcular_hash(path),
        "resultado": resultado,
        "timestamp": datetime.now().isoformat()
    }
    
    _guardar_cache(cache)


def estadisticas_cache() -> dict:
    """Regresa cuántos archivos hay en caché — útil para el log."""
    cache = _cargar_cache()
    return {
        "archivos_en_cache": len(cache),
        "archivo_cache": CACHE_FILE
    }


def limpiar_cache() -> None:
    """Elimina el archivo de caché. Útil para forzar un análisis completo."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
