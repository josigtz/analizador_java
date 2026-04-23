"""
main.py — Agente principal de análisis de proyectos Java

Este archivo orquesta todo:
  1. Define las herramientas que Claude puede usar
  2. Ejecuta el loop del agente hasta generar los 3 reportes
  3. Activa el modo interactivo para preguntas posteriores
"""

import anthropic
import json
import sys
import os
from herramientas import (
    escanear_proyecto, leer_archivo, buscar_archivos,
    analizar_deuda_tecnica, analizar_seguridad,
    analizar_cobertura_tests, calcular_metricas,
    generar_diagrama_mermaid, guardar_reporte
)
from logger import AnalizadorLogger
from cache import estadisticas_cache


# ── Cliente de Anthropic ─────────────────────────────────────────────────────
client = anthropic.Anthropic()


# ── Definición de herramientas para Claude ───────────────────────────────────
# Aquí le decimos a Claude QUÉ herramientas existen.
# La descripción es crucial — Claude la usa para decidir cuándo llamar cada una.

TOOLS = [
    {
        "name": "escanear_proyecto",
        "description": "Escanea la estructura completa del proyecto Java. SIEMPRE llamar primero.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ruta": {"type": "string", "description": "Ruta raíz del proyecto"}
            },
            "required": ["ruta"]
        }
    },
    {
        "name": "leer_archivo",
        "description": "Lee el contenido de un archivo específico (Java, pom.xml, yml, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta completa del archivo"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "buscar_archivos",
        "description": "Busca archivos que contengan un texto o anotación específica",
        "input_schema": {
            "type": "object",
            "properties": {
                "ruta":   {"type": "string", "description": "Ruta donde buscar"},
                "patron": {"type": "string", "description": "Texto a buscar dentro de los archivos"}
            },
            "required": ["ruta", "patron"]
        }
    },
    {
        "name": "analizar_deuda_tecnica",
        "description": "Analiza un archivo Java en busca de métodos largos, TODOs y código de baja calidad",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta del archivo .java a analizar"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "analizar_seguridad",
        "description": "Detecta vulnerabilidades de seguridad en un archivo Java",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta del archivo .java a analizar"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "analizar_cobertura_tests",
        "description": "Compara clases de producción con archivos de test existentes",
        "input_schema": {
            "type": "object",
            "properties": {
                "ruta":        {"type": "string", "description": "Ruta raíz del proyecto"},
                "controllers": {"type": "array", "items": {"type": "string"},
                                "description": "Lista de rutas de los controllers"}
            },
            "required": ["ruta", "controllers"]
        }
    },
    {
        "name": "calcular_metricas",
        "description": "Calcula métricas cuantitativas: líneas de código, clases, endpoints, ratio de tests",
        "input_schema": {
            "type": "object",
            "properties": {
                "ruta":    {"type": "string", "description": "Ruta raíz del proyecto"},
                "escaneo": {"type": "string", "description": "Resultado del escaneo en JSON"}
            },
            "required": ["ruta", "escaneo"]
        }
    },
    {
        "name": "generar_diagrama_mermaid",
        "description": "Genera el diagrama de arquitectura en formato Mermaid",
        "input_schema": {
            "type": "object",
            "properties": {
                "controllers": {"type": "array", "items": {"type": "string"}},
                "services":    {"type": "array", "items": {"type": "string"}},
                "repositorios": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["controllers", "services", "repositorios"]
        }
    },
    {
        "name": "guardar_reporte",
        "description": "Guarda un reporte Markdown en disco. Usar tres veces: ejecutivo, tecnico y apis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre":    {"type": "string",
                              "description": "Nombre del archivo, ej: reporte_ejecutivo.md"},
                "contenido": {"type": "string", "description": "Contenido completo del reporte en Markdown"}
            },
            "required": ["nombre", "contenido"]
        }
    }
]


# ── Dispatcher de herramientas ───────────────────────────────────────────────
# Conecta el nombre que Claude envía con la función Python real.

def execute_tool(name: str, tool_input: dict, log: AnalizadorLogger,
                 escaneo_global: dict) -> str:
    """
    Ejecuta la herramienta solicitada por Claude.
    
    escaneo_global: guardamos el resultado del escaneo inicial para
    reutilizarlo sin tener que re-escanear el proyecto en cada llamada.
    """
    
    if name == "escanear_proyecto":
        resultado = escanear_proyecto(tool_input["ruta"], log)
        # Guardamos en escaneo_global para que otras herramientas lo usen
        escaneo_global.update(resultado)
        return json.dumps(resultado, ensure_ascii=False)
    
    elif name == "leer_archivo":
        return leer_archivo(tool_input["path"], log)
    
    elif name == "buscar_archivos":
        resultado = buscar_archivos(tool_input["ruta"], tool_input["patron"], log)
        return json.dumps(resultado, ensure_ascii=False)
    
    elif name == "analizar_deuda_tecnica":
        resultado = analizar_deuda_tecnica(tool_input["path"], log)
        return json.dumps(resultado, ensure_ascii=False)
    
    elif name == "analizar_seguridad":
        resultado = analizar_seguridad(tool_input["path"], log)
        return json.dumps(resultado, ensure_ascii=False)
    
    elif name == "analizar_cobertura_tests":
        resultado = analizar_cobertura_tests(
            tool_input["ruta"],
            tool_input.get("controllers", escaneo_global.get("controllers", [])),
            log
        )
        return json.dumps(resultado, ensure_ascii=False)
    
    elif name == "calcular_metricas":
        # Claude pasa el escaneo como string JSON — lo convertimos
        escaneo = json.loads(tool_input.get("escaneo", "{}")) if isinstance(
            tool_input.get("escaneo"), str) else escaneo_global
        resultado = calcular_metricas(tool_input["ruta"], escaneo_global, log)
        return json.dumps(resultado, ensure_ascii=False)
    
    elif name == "generar_diagrama_mermaid":
        return generar_diagrama_mermaid(
            tool_input.get("controllers", escaneo_global.get("controllers", [])),
            tool_input.get("services",    escaneo_global.get("services", [])),
            tool_input.get("repositorios", escaneo_global.get("repositorios", [])),
            log
        )
    
    elif name == "guardar_reporte":
        return guardar_reporte(tool_input["nombre"], tool_input["contenido"], log)
    
    else:
        return f"Herramienta desconocida: {name}"


# ── Sistema prompt del agente ────────────────────────────────────────────────
# Le damos instrucciones claras sobre qué debe generar y en qué orden.

SYSTEM_PROMPT = """Eres un experto en análisis de proyectos Java empresariales.

Tu tarea es analizar el proyecto y generar TRES reportes separados en Markdown.

ORDEN DE TRABAJO:
1. Llama a escanear_proyecto para entender la estructura
2. Lee pom.xml o build.gradle para identificar tecnologías
3. Lee los Controllers para documentar APIs
4. Lee los Services más importantes para entender la lógica
5. Analiza deuda técnica y seguridad en los Controllers principales
6. Calcula métricas y cobertura de tests
7. Genera el diagrama Mermaid
8. Guarda los tres reportes con guardar_reporte

TRES REPORTES A GENERAR:

**reporte_ejecutivo.md** (para gerencia, sin tecnicismos):
- Qué hace el sistema en lenguaje simple
- Principales funcionalidades (máximo 7 bullets)
- Integraciones con sistemas externos
- Riesgos detectados en lenguaje de negocio
- Métricas de salud del proyecto (% cobertura, nivel de deuda)

**reporte_tecnico.md** (para el equipo de desarrollo):
- Stack completo con versiones
- Diagrama de arquitectura Mermaid
- Patrones y convenciones detectadas
- Métricas detalladas (clases, endpoints, líneas)
- Deuda técnica por archivo con números de línea
- Vulnerabilidades de seguridad detectadas
- Casos de prueba sugeridos por funcionalidad

**reporte_apis.md** (documentación de APIs, para todos):
Por cada endpoint encontrado:
  - Método HTTP + ruta
  - Descripción en lenguaje natural
  - Tabla de parámetros con tipos y si son requeridos
  - Ejemplo de request JSON
  - Ejemplo de response exitoso (200) en JSON
  - Ejemplo de response de error (4xx) en JSON
  - Casos de prueba sugeridos (mínimo 4 por endpoint)

IMPORTANTE:
- Para proyectos grandes (>100 clases), prioriza Controllers y Services principales
- Si un endpoint no tiene cuerpo JSON (GET simple), indica que no aplica
- Genera ejemplos JSON realistas, no genéricos como "string" o 0
- Los tres reportes deben guardarse con guardar_reporte antes de terminar"""


# ── Loop principal del agente ────────────────────────────────────────────────

def run_agent(ruta_proyecto: str) -> dict:
    """
    Ejecuta el agente de análisis completo.
    Regresa un dict con las rutas de los reportes generados.
    """
    nombre_proyecto = os.path.basename(ruta_proyecto.rstrip("/\\"))
    log = AnalizadorLogger(nombre_proyecto)
    escaneo_global = {}  # Se llena cuando el agente llama escanear_proyecto
    
    cache_stats = estadisticas_cache()
    log.decision_agente(f"Caché: {cache_stats['archivos_en_cache']} archivos previos disponibles")
    
    messages = [{
        "role": "user",
        "content": (
            f"Analiza el proyecto Java en la ruta: {ruta_proyecto}\n"
            f"Genera los tres reportes completos: ejecutivo, técnico y de APIs."
        )
    }]
    
    reportes_generados = {}
    
    print(f"\n{'='*60}")
    print(f"  Analizador de Proyectos Java ")
    print(f"  Proyecto: {nombre_proyecto}")
    print(f"{'='*60}\n")
    
    # ── Loop del agente
    while True:
        log.llamada_ia("análisis y generación de reporte")
        
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8096,   # Máximo para reportes largos
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input, log, escaneo_global)
                    
                    # Detectar si se guardó un reporte para la lista final
                    if block.name == "guardar_reporte":
                        nombre = block.input.get("nombre", "")
                        reportes_generados[nombre] = f"reportes/{nombre}"
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            messages.append({"role": "user", "content": tool_results})
        
        else:
            # El agente terminó
            break
    
    log_path = log.finalizar()
    
    print(f"\n{'='*60}")
    print("  ✅ Análisis completado")
    print(f"{'='*60}")
    for nombre, path in reportes_generados.items():
        print(f"  📄 {path}")
    print(f"  📋 {log_path}")
    print(f"{'='*60}\n")
    
    return {
        "reportes": reportes_generados,
        "log": log_path,
        "messages": messages,        # Los pasamos al modo interactivo
        "escaneo": escaneo_global
    }


# ── Modo interactivo ─────────────────────────────────────────────────────────

def modo_interactivo(contexto: dict) -> None:
    """
    Después de generar el reporte, el usuario puede hacer preguntas
    sobre el proyecto en lenguaje natural.
    
    El agente ya tiene todo el contexto de la conversación anterior
    (messages), así que no necesita volver a leer el código.
    """
    messages = contexto["messages"]
    
    print("💬 Modo interactivo activado. Puedes preguntarme sobre el proyecto.")
    print("   Ejemplos:")
    print("   - ¿Cómo funciona el flujo de autenticación?")
    print("   - ¿Qué endpoints no tienen pruebas?")
    print("   - Explícame la clase ClienteService")
    print("   - ¿Cuáles son los mayores riesgos de seguridad?")
    print("   Escribe 'salir' para terminar.\n")
    
    while True:
        # input() lee una línea de texto del usuario en consola
        pregunta = input("🧑 Tú: ").strip()
        
        if not pregunta:
            continue
        
        if pregunta.lower() in ("salir", "exit", "quit"):
            print("\n👋 Análisis finalizado.")
            break
        
        messages.append({"role": "user", "content": pregunta})
        
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,   # Puede seguir usando herramientas si necesita releer algo
            messages=messages
        )
        
        # En el modo interactivo también manejamos tool_use
        # (el agente puede querer releer un archivo para responder mejor)
        escaneo_global = contexto.get("escaneo", {})
        log_interactivo = AnalizadorLogger("interactivo")
        
        while response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input,
                                         log_interactivo, escaneo_global)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            messages.append({"role": "user", "content": tool_results})
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )
        
        # Extraer y mostrar la respuesta final
        respuesta = next(
            (b.text for b in response.content if hasattr(b, "text")), ""
        )
        messages.append({"role": "assistant", "content": respuesta})
        print(f"\n🤖 Claude: {respuesta}\n")


# ── Punto de entrada ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    sys.argv contiene los argumentos de línea de comando.
    sys.argv[0] = nombre del script
    sys.argv[1] = primer argumento (la ruta del proyecto)
    
    Uso: python main.py /ruta/a/tu/proyecto
    """
    
    if len(sys.argv) < 2:
        # Si no se pasa ruta, pedirla interactivamente
        ruta = input("📁 Ruta del proyecto Java: ").strip()
    else:
        ruta = sys.argv[1]
    
    if not os.path.exists(ruta):
        print(f"❌ Error: la ruta '{ruta}' no existe")
        sys.exit(1)  # sys.exit(1) termina el programa con código de error
    
    # Ejecutar el análisis completo
    contexto = run_agent(ruta)
    
    # Preguntar si quiere usar el modo interactivo
    respuesta = input("\n¿Quieres hacer preguntas sobre el proyecto? (s/n): ").strip().lower()
    if respuesta == "s":
        modo_interactivo(contexto)
