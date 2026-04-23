"""
herramientas.py — Implementación de todas las herramientas del agente

Aquí vive la lógica REAL. Claude decide cuándo llamar cada herramienta,
pero Python es quien las ejecuta.

Regla de oro aplicada en cada herramienta:
  ✅ Python puro  → escanear, leer, buscar, detectar patrones, métricas
  🤖 IA (Claude) → interpretar, redactar, inferir intención de negocio
"""

import os
import re
import json
from pathlib import Path     # Manejo de rutas más elegante que os.path
from typing import Optional
from cache import obtener_cache, guardar_en_cache
from logger import AnalizadorLogger


# ── Constantes ───────────────────────────────────────────────────────────────

# Extensiones que nos interesan analizar
EXTENSIONES_JAVA = {".java", ".xml", ".gradle", ".properties", ".yml", ".yaml"}

# Archivos/carpetas que siempre ignoramos
IGNORAR = {
    "target", "build", ".git", ".idea", ".mvn",
    "node_modules", "__pycache__", ".class"
}

# Anotaciones de Spring que identifican cada tipo de clase
ANOTACIONES_CONTROLLER = ["@RestController", "@Controller"]
ANOTACIONES_SERVICE     = ["@Service", "@Component"]
ANOTACIONES_REPO        = ["@Repository"]
ANOTACIONES_ENDPOINT    = ["@GetMapping", "@PostMapping", "@PutMapping",
                           "@DeleteMapping", "@PatchMapping", "@RequestMapping"]
ANOTACIONES_SEGURIDAD   = ["@PreAuthorize", "@Secured", "@RolesAllowed"]


# ── 1. Escanear proyecto ─────────────────────────────────────────────────────

def escanear_proyecto(ruta: str, log: AnalizadorLogger) -> dict:
    """
    Recorre el proyecto y construye un mapa de su estructura.
    
    Path() es la forma moderna de manejar rutas en Python.
    rglob("*") busca recursivamente todos los archivos.
    
    Returns: dict con estructura, conteos y archivos clave encontrados.
    """
    log.herramienta_usada("escanear_proyecto", {"ruta": ruta})
    
    raiz = Path(ruta)
    if not raiz.exists():
        return {"error": f"La ruta '{ruta}' no existe"}
    
    estructura = []     # Lista de líneas del árbol de directorios
    archivos_por_tipo = {"java": [], "xml": [], "config": [], "otros": []}
    controllers = []
    services    = []
    repos       = []
    
    # os.walk recorre carpetas recursivamente
    # raiz_dir = carpeta actual, dirs = subcarpetas, archivos = archivos
    for raiz_dir, dirs, archivos in os.walk(ruta):
        
        # Modificar 'dirs' en el lugar excluye esas carpetas del recorrido
        # La sintaxis [:] modifica la lista original (no crea una nueva)
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        
        # Calcular nivel de profundidad para la indentación del árbol
        nivel = raiz_dir.replace(ruta, "").count(os.sep)
        indent = "  " * nivel
        nombre_carpeta = os.path.basename(raiz_dir)
        estructura.append(f"{indent}📁 {nombre_carpeta}/")
        
        for archivo in sorted(archivos):
            ext = Path(archivo).suffix
            if ext in EXTENSIONES_JAVA:
                path_completo = os.path.join(raiz_dir, archivo)
                estructura.append(f"{indent}  📄 {archivo}")
                
                # Clasificar por tipo
                if ext == ".java":
                    archivos_por_tipo["java"].append(path_completo)
                    
                    # Leer las primeras líneas para detectar tipo de clase
                    try:
                        with open(path_completo, "r", encoding="utf-8", errors="ignore") as f:
                            primeras_lineas = "".join(f.readlines()[:20])
                        
                        if any(a in primeras_lineas for a in ANOTACIONES_CONTROLLER):
                            controllers.append(path_completo)
                        elif any(a in primeras_lineas for a in ANOTACIONES_SERVICE):
                            services.append(path_completo)
                        elif any(a in primeras_lineas for a in ANOTACIONES_REPO):
                            repos.append(path_completo)
                    except Exception:
                        pass
                
                elif archivo in ("pom.xml", "build.gradle", "settings.gradle"):
                    archivos_por_tipo["xml"].append(path_completo)
                elif ext in (".properties", ".yml", ".yaml"):
                    archivos_por_tipo["config"].append(path_completo)
    
    total_java = len(archivos_por_tipo["java"])
    log.decision_agente(
        f"Proyecto escaneado: {total_java} clases Java, "
        f"{len(controllers)} controllers, {len(services)} services"
    )
    
    return {
        "estructura": "\n".join(estructura[:100]),  # Máximo 100 líneas del árbol
        "total_clases": total_java,
        "controllers": controllers,
        "services": services,
        "repositorios": repos,
        "archivos_config": archivos_por_tipo["config"],
        "archivos_build": archivos_por_tipo["xml"],
        "tamaño": "pequeño" if total_java < 20 else "mediano" if total_java < 100 else "grande"
    }


# ── 2. Leer archivo ──────────────────────────────────────────────────────────

def leer_archivo(path: str, log: AnalizadorLogger,
                 usar_cache: bool = True) -> str:
    """
    Lee un archivo con soporte de caché.
    
    Si el archivo no cambió desde el último análisis, devuelve el
    resultado cacheado sin leerlo de nuevo.
    """
    log.herramienta_usada("leer_archivo", {"path": path})
    
    if not os.path.exists(path):
        log.error("leer_archivo", f"Archivo no encontrado: {path}")
        return f"Error: archivo '{path}' no encontrado"
    
    # Revisar caché primero
    if usar_cache:
        resultado_cacheado = obtener_cache(path)
        if resultado_cacheado:
            log.cache_usado(path)
            return resultado_cacheado
    
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            contenido = f.read()
        
        lineas = contenido.count("\n")
        log.archivo_leido(path, lineas)
        
        # Si es muy largo, truncar e indicarlo
        # Esto evita mandar demasiados tokens a la IA
        MAX_CHARS = 15_000  # El guión bajo en números es válido en Python (legibilidad)
        if len(contenido) > MAX_CHARS:
            contenido = contenido[:MAX_CHARS] + f"\n\n... [archivo truncado, {lineas} líneas totales]"
        
        return contenido
        
    except Exception as e:
        log.error("leer_archivo", str(e))
        return f"Error leyendo archivo: {str(e)}"


# ── 3. Buscar archivos ───────────────────────────────────────────────────────

def buscar_archivos(ruta: str, patron: str, log: AnalizadorLogger) -> list:
    """
    Busca archivos que contengan un patrón de texto.
    
    Útil para encontrar, por ejemplo, todos los archivos que usan
    @Transactional o que importan una librería específica.
    
    glob() busca por nombre de archivo, grep() busca dentro del contenido.
    Aquí hacemos ambos.
    """
    log.herramienta_usada("buscar_archivos", {"ruta": ruta, "patron": patron})
    
    encontrados = []
    
    for raiz_dir, dirs, archivos in os.walk(ruta):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        
        for archivo in archivos:
            if not archivo.endswith(".java"):
                continue
            
            path = os.path.join(raiz_dir, archivo)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    contenido = f.read()
                
                if patron in contenido:
                    encontrados.append(path)
            except Exception:
                pass
    
    return encontrados


# ── 4. Analizar deuda técnica ────────────────────────────────────────────────

def analizar_deuda_tecnica(path: str, log: AnalizadorLogger) -> dict:
    """
    Detecta problemas de calidad en un archivo Java.
    Todo Python puro — no necesita IA.
    
    Detecta:
    - Métodos muy largos (> 40 líneas)
    - TODOs y FIXMEs
    - Clases con demasiados métodos (posible violación de SRP)
    - Código comentado (señal de deuda técnica)
    """
    log.herramienta_usada("analizar_deuda_tecnica", {"path": path})
    
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lineas = f.readlines()
    except Exception as e:
        return {"error": str(e)}
    
    problemas = []
    
    # ── Detectar TODOs y FIXMEs
    for i, linea in enumerate(lineas, 1):  # enumerate(lista, 1) empieza en línea 1
        linea_upper = linea.upper()
        if "TODO" in linea_upper or "FIXME" in linea_upper or "HACK" in linea_upper:
            problemas.append({
                "tipo": "TODO/FIXME",
                "linea": i,
                "texto": linea.strip()
            })
    
    # ── Detectar métodos largos
    # Buscamos "public/private/protected ... {" y contamos hasta el cierre
    en_metodo = False
    inicio_metodo = 0
    nombre_metodo = ""
    profundidad = 0  # Contador de llaves {} para saber cuándo termina el método
    
    patron_metodo = re.compile(
        r'\s*(public|private|protected|static)\s+[\w<>\[\]]+\s+(\w+)\s*\('
    )
    
    for i, linea in enumerate(lineas, 1):
        match = patron_metodo.search(linea)
        if match and not en_metodo:
            en_metodo = True
            inicio_metodo = i
            nombre_metodo = match.group(2)
            profundidad = 0
        
        if en_metodo:
            profundidad += linea.count("{") - linea.count("}")
            if profundidad <= 0 and i > inicio_metodo:
                longitud = i - inicio_metodo
                if longitud > 40:
                    problemas.append({
                        "tipo": "método_largo",
                        "linea": inicio_metodo,
                        "texto": f"Método '{nombre_metodo}' tiene {longitud} líneas (recomendado: < 40)"
                    })
                en_metodo = False
    
    # ── Detectar código comentado (bloques de código entre /* */ o // seguidos)
    lineas_comentadas = 0
    for linea in lineas:
        stripped = linea.strip()
        if stripped.startswith("//") and any(
            keyword in stripped for keyword in ["= new", "return", "if (", "for (", ".get("]
        ):
            lineas_comentadas += 1
    
    if lineas_comentadas > 5:
        problemas.append({
            "tipo": "codigo_comentado",
            "linea": 0,
            "texto": f"Se detectaron ~{lineas_comentadas} líneas de código comentado"
        })
    
    # ── Contar métodos públicos (más de 20 sugiere violación de SRP)
    metodos_publicos = len(re.findall(r'\bpublic\s+\w+.*\(', "".join(lineas)))
    if metodos_publicos > 20:
        problemas.append({
            "tipo": "clase_grande",
            "linea": 1,
            "texto": f"La clase tiene {metodos_publicos} métodos públicos (posible violación de SRP)"
        })
    
    return {
        "archivo": path,
        "total_lineas": len(lineas),
        "problemas": problemas,
        "nivel_deuda": "alto" if len(problemas) > 5 else "medio" if len(problemas) > 2 else "bajo"
    }


# ── 5. Analizar seguridad ────────────────────────────────────────────────────

def analizar_seguridad(path: str, log: AnalizadorLogger) -> dict:
    """
    Detecta vulnerabilidades comunes en código Java.
    
    Detecta:
    - Credenciales hardcodeadas (passwords, tokens, secrets)
    - Queries con concatenación de strings (riesgo SQL injection)
    - Endpoints sin anotación de seguridad
    - Uso de algoritmos débiles (MD5, SHA1 para contraseñas)
    """
    log.herramienta_usada("analizar_seguridad", {"path": path})
    
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            contenido = f.read()
            lineas = contenido.splitlines()
    except Exception as e:
        return {"error": str(e)}
    
    vulnerabilidades = []
    
    # ── Credenciales hardcodeadas
    # re.IGNORECASE hace la búsqueda case-insensitive
    patrones_credenciales = [
        (r'password\s*=\s*"[^"]+"',    "Posible contraseña hardcodeada"),
        (r'secret\s*=\s*"[^"]+"',      "Posible secret hardcodeado"),
        (r'api[_-]?key\s*=\s*"[^"]+"', "Posible API key hardcodeada"),
        (r'token\s*=\s*"[^"]+"',       "Posible token hardcodeado"),
    ]
    
    for i, linea in enumerate(lineas, 1):
        for patron, descripcion in patrones_credenciales:
            if re.search(patron, linea, re.IGNORECASE):
                # Excluir comentarios y tests
                if not linea.strip().startswith("//") and "test" not in path.lower():
                    vulnerabilidades.append({
                        "tipo": "credencial_expuesta",
                        "severidad": "alta",
                        "linea": i,
                        "descripcion": descripcion
                    })
    
    # ── SQL Injection: queries construidas con concatenación
    if re.search(r'"SELECT.*"\s*\+', contenido, re.IGNORECASE):
        vulnerabilidades.append({
            "tipo": "sql_injection",
            "severidad": "alta",
            "linea": 0,
            "descripcion": "Query SQL construida con concatenación (+). Usar PreparedStatement o JPA."
        })
    
    # ── Endpoints sin seguridad
    tiene_endpoints = any(a in contenido for a in ANOTACIONES_ENDPOINT)
    tiene_seguridad = any(a in contenido for a in ANOTACIONES_SEGURIDAD)
    
    if tiene_endpoints and not tiene_seguridad:
        vulnerabilidades.append({
            "tipo": "endpoint_sin_seguridad",
            "severidad": "media",
            "linea": 0,
            "descripcion": "Este Controller tiene endpoints sin anotaciones de seguridad (@PreAuthorize, @Secured)"
        })
    
    # ── Algoritmos débiles para contraseñas
    if re.search(r'MessageDigest\.getInstance\("MD5"\)', contenido):
        vulnerabilidades.append({
            "tipo": "algoritmo_debil",
            "severidad": "alta",
            "linea": 0,
            "descripcion": "MD5 no debe usarse para contraseñas. Usar BCrypt o Argon2."
        })
    
    return {
        "archivo": path,
        "vulnerabilidades": vulnerabilidades,
        "nivel_riesgo": "alto" if any(v["severidad"] == "alta" for v in vulnerabilidades)
                        else "medio" if vulnerabilidades else "bajo"
    }


# ── 6. Analizar cobertura de tests ───────────────────────────────────────────

def analizar_cobertura_tests(ruta: str, controllers: list,
                              log: AnalizadorLogger) -> dict:
    """
    Compara clases de producción con sus respectivos tests.
    
    Busca el patrón Java estándar: ClienteService → ClienteServiceTest
    """
    log.herramienta_usada("analizar_cobertura_tests", {"ruta": ruta})
    
    # Buscar todos los archivos de test
    archivos_test = []
    for raiz_dir, dirs, archivos in os.walk(ruta):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for archivo in archivos:
            # Los tests suelen estar en src/test/ o terminar en Test.java
            if archivo.endswith("Test.java") or "test" in raiz_dir.lower():
                archivos_test.append(archivo.replace("Test.java", ".java"))
    
    # Comparar controllers con sus tests
    sin_test = []
    con_test = []
    
    for controller_path in controllers:
        nombre_clase = Path(controller_path).name  # Solo el nombre del archivo
        if nombre_clase in archivos_test:
            con_test.append(nombre_clase)
        else:
            sin_test.append(nombre_clase)
    
    total = len(controllers)
    cobertura = (len(con_test) / total * 100) if total > 0 else 0
    
    return {
        "total_controllers": total,
        "con_test": con_test,
        "sin_test": sin_test,
        "cobertura_porcentaje": round(cobertura, 1),
        "total_archivos_test": len(archivos_test)
    }


# ── 7. Calcular métricas ─────────────────────────────────────────────────────

def calcular_metricas(ruta: str, escaneo: dict, log: AnalizadorLogger) -> dict:
    """
    Métricas cuantitativas del proyecto.
    Todo calculable sin IA.
    """
    log.herramienta_usada("calcular_metricas", {"ruta": ruta})
    
    total_lineas = 0
    total_clases = escaneo.get("total_clases", 0)
    total_interfaces = 0
    total_enums = 0
    total_endpoints = 0
    
    for raiz_dir, dirs, archivos in os.walk(ruta):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        
        for archivo in archivos:
            if not archivo.endswith(".java"):
                continue
            
            path = os.path.join(raiz_dir, archivo)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    contenido = f.read()
                    total_lineas += contenido.count("\n")
                
                if "interface " in contenido:
                    total_interfaces += 1
                if "enum " in contenido:
                    total_enums += 1
                
                # Contar endpoints
                for anotacion in ANOTACIONES_ENDPOINT:
                    total_endpoints += contenido.count(anotacion)
                    
            except Exception:
                pass
    
    archivos_test = len([
        f for f in Path(ruta).rglob("*Test.java")
        if not any(ig in str(f) for ig in IGNORAR)
    ])
    
    ratio_test = round(archivos_test / total_clases * 100, 1) if total_clases > 0 else 0
    
    return {
        "total_lineas_codigo": total_lineas,
        "total_clases": total_clases,
        "total_interfaces": total_interfaces,
        "total_enums": total_enums,
        "total_endpoints": total_endpoints,
        "total_controllers": len(escaneo.get("controllers", [])),
        "total_services": len(escaneo.get("services", [])),
        "total_repositorios": len(escaneo.get("repositorios", [])),
        "archivos_test": archivos_test,
        "ratio_test_pct": ratio_test
    }


# ── 8. Generar diagrama Mermaid ──────────────────────────────────────────────

def generar_diagrama_mermaid(controllers: list, services: list,
                              repositorios: list, log: AnalizadorLogger) -> str:
    """
    Genera un diagrama de arquitectura en formato Mermaid.
    
    Mermaid es un lenguaje de texto que se renderiza como diagrama
    en GitHub, Notion, GitLab, y muchos editores Markdown.
    
    Inferimos las dependencias por los imports de cada archivo.
    """
    log.herramienta_usada("generar_diagrama_mermaid", {
        "controllers": len(controllers),
        "services": len(services)
    })
    
    # Extraer nombre simple de cada clase (sin ruta ni extensión)
    def nombre_clase(path: str) -> str:
        return Path(path).stem  # stem = nombre sin extensión
    
    relaciones = []
    
    # Para cada controller, buscar qué services importa o inyecta
    for ctrl_path in controllers:
        ctrl_nombre = nombre_clase(ctrl_path)
        try:
            with open(ctrl_path, "r", encoding="utf-8", errors="ignore") as f:
                contenido = f.read()
            
            for svc_path in services:
                svc_nombre = nombre_clase(svc_path)
                # Si el controller menciona el service (inyección de dependencias)
                if svc_nombre in contenido:
                    relaciones.append(f"    {ctrl_nombre} --> {svc_nombre}")
        except Exception:
            pass
    
    # Para cada service, buscar qué repositorios usa
    for svc_path in services:
        svc_nombre = nombre_clase(svc_path)
        try:
            with open(svc_path, "r", encoding="utf-8", errors="ignore") as f:
                contenido = f.read()
            
            for repo_path in repositorios:
                repo_nombre = nombre_clase(repo_path)
                if repo_nombre in contenido:
                    relaciones.append(f"    {svc_nombre} --> {repo_nombre}")
                    relaciones.append(f"    {repo_nombre} --> DB[(Base de Datos)]")
        except Exception:
            pass
    
    # Si no encontramos relaciones, hacer diagrama genérico por capas
    if not relaciones:
        ctrl_nombres = [nombre_clase(p) for p in controllers[:5]]
        svc_nombres  = [nombre_clase(p) for p in services[:5]]
        repo_nombres = [nombre_clase(p) for p in repositorios[:3]]
        
        for c in ctrl_nombres:
            for s in svc_nombres[:2]:
                relaciones.append(f"    {c} --> {s}")
        for s in svc_nombres:
            for r in repo_nombres[:1]:
                relaciones.append(f"    {s} --> {r}")
        if repo_nombres:
            relaciones.append(f"    {repo_nombres[0]} --> DB[(Base de Datos)]")
    
    # Eliminar duplicados preservando orden
    # dict.fromkeys() es el truco idiomático de Python para esto
    relaciones_unicas = list(dict.fromkeys(relaciones))
    
    diagrama = "```mermaid\ngraph TD\n"
    diagrama += "\n".join(relaciones_unicas)
    diagrama += "\n```"
    
    return diagrama


# ── 9. Guardar reporte ───────────────────────────────────────────────────────

def guardar_reporte(nombre: str, contenido: str, log: AnalizadorLogger) -> str:
    """
    Guarda un archivo Markdown en la carpeta reportes/.
    Regresa la ruta donde se guardó.
    """
    log.herramienta_usada("guardar_reporte", {"nombre": nombre})
    
    os.makedirs("reportes", exist_ok=True)
    path = f"reportes/{nombre}"
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    
    log.reporte_generado(nombre, path)
    return path
