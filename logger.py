"""
logger.py — Registro de análisis del agente

¿Por qué existe este módulo?
Un agente profesional debe ser transparente: el usuario necesita saber
exactamente qué archivos leyó, cuáles ignoró y por qué, y si hubo errores.

Este módulo genera dos salidas simultáneas:
  1. Consola: mensajes en tiempo real mientras el agente trabaja
  2. Archivo analisis.log: registro completo para auditoría posterior

Conceptos de Python que verás aquí:
  - Enum: tipo con valores fijos (como enum en Java)
  - logging: módulo built-in de Python para logs estructurados
  - f-strings multilínea
"""

import logging
import os
from datetime import datetime
from enum import Enum


# Enum para categorizar cada entrada del log
# En Python, Enum se hereda como clase
class TipoLog(Enum):
    INICIO      = "🚀 INICIO"
    ARCHIVO_OK  = "📄 LEÍDO"
    CACHE_HIT   = "⚡ CACHÉ"
    IGNORADO    = "⏭  IGNORADO"
    HERRAMIENTA = "🔧 HERRAMIENTA"
    IA_LLAMADA  = "🤖 IA"
    REPORTE     = "📊 REPORTE"
    ERROR       = "❌ ERROR"
    DECISION    = "💭 DECISIÓN"
    FIN         = "✅ FIN"


class AnalizadorLogger:
    """
    Logger personalizado para el agente.
    
    En Python, las clases se definen con 'class NombreClase:'
    __init__ es el constructor (equivale a public NombreClase() en Java)
    self es la referencia al objeto actual (equivale a 'this' en Java)
    """
    
    def __init__(self, proyecto: str):
        self.proyecto = proyecto
        self.entradas = []  # Lista de todas las entradas del log
        self.inicio = datetime.now()
        
        # Crear carpeta de reportes si no existe
        os.makedirs("reportes", exist_ok=True)
        
        # Nombre del archivo de log con timestamp
        timestamp = self.inicio.strftime("%Y%m%d_%H%M%S")
        self.log_file = f"reportes/analisis_{timestamp}.log"
        
        # Configurar el sistema de logging de Python
        # Esto escribe al archivo Y a la consola simultáneamente
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",  # Solo el mensaje, sin prefijos de Python
            handlers=[
                logging.FileHandler(self.log_file, encoding="utf-8"),
                logging.StreamHandler()  # También muestra en consola
            ]
        )
        
        self.logger = logging.getLogger("analizador")
        self._registrar(TipoLog.INICIO, f"Proyecto: {proyecto}")
    
    def _registrar(self, tipo: TipoLog, mensaje: str, detalle: str = "") -> None:
        """
        Método interno que registra una entrada en el log.
        
        El parámetro 'detalle=""' tiene un valor por defecto —
        si no se pasa, Python usa el string vacío automáticamente.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Construir la línea del log
        linea = f"[{timestamp}] {tipo.value} — {mensaje}"
        if detalle:
            linea += f"\n           {detalle}"
        
        # Guardar en lista interna (para el resumen final)
        self.entradas.append({
            "tipo": tipo.name,
            "mensaje": mensaje,
            "timestamp": timestamp
        })
        
        # Escribir al archivo y consola
        self.logger.info(linea)
    
    # Métodos públicos — uno por tipo de evento
    
    def archivo_leido(self, path: str, lineas: int) -> None:
        self._registrar(TipoLog.ARCHIVO_OK, path, f"{lineas} líneas")
    
    def cache_usado(self, path: str) -> None:
        self._registrar(TipoLog.CACHE_HIT, path, "resultado anterior reutilizado")
    
    def archivo_ignorado(self, path: str, razon: str) -> None:
        self._registrar(TipoLog.IGNORADO, path, f"Razón: {razon}")
    
    def herramienta_usada(self, nombre: str, params: dict) -> None:
        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        self._registrar(TipoLog.HERRAMIENTA, nombre, params_str)
    
    def llamada_ia(self, proposito: str, tokens_aprox: int = 0) -> None:
        detalle = f"Propósito: {proposito}"
        if tokens_aprox:
            detalle += f" | ~{tokens_aprox} tokens"
        self._registrar(TipoLog.IA_LLAMADA, "Claude API", detalle)
    
    def decision_agente(self, decision: str) -> None:
        self._registrar(TipoLog.DECISION, decision)
    
    def reporte_generado(self, nombre: str, path: str) -> None:
        self._registrar(TipoLog.REPORTE, nombre, f"Guardado en: {path}")
    
    def error(self, contexto: str, error: str) -> None:
        self._registrar(TipoLog.ERROR, contexto, error)
    
    def finalizar(self) -> str:
        """
        Genera y registra el resumen final del análisis.
        Regresa la ruta del archivo de log.
        """
        duracion = (datetime.now() - self.inicio).seconds
        
        # Contar eventos por tipo usando comprensión de diccionario
        conteos = {}
        for entrada in self.entradas:
            tipo = entrada["tipo"]
            # setdefault: si la clave no existe, la crea con valor 0
            conteos.setdefault(tipo, 0)
            conteos[tipo] += 1
        
        resumen = f"""
{'='*60}
RESUMEN DEL ANÁLISIS
{'='*60}
Proyecto  : {self.proyecto}
Duración  : {duracion} segundos
Archivos leídos   : {conteos.get('ARCHIVO_OK', 0)}
Caché usado       : {conteos.get('CACHE_HIT', 0)} veces
Archivos ignorados: {conteos.get('IGNORADO', 0)}
Llamadas a IA     : {conteos.get('IA_LLAMADA', 0)}
Errores           : {conteos.get('ERROR', 0)}
Log guardado en   : {self.log_file}
{'='*60}
"""
        self.logger.info(resumen)
        return self.log_file
