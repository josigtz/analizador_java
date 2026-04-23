# Analizador de Proyectos Java — V3 Profesional

Agente de IA que analiza proyectos Java y genera tres reportes automáticos: uno ejecutivo, uno técnico y uno de APIs con ejemplos JSON reales.

---

## ¿Qué hace?

Le das la ruta de cualquier proyecto Java y el agente:

1. Escanea la estructura completa del proyecto
2. Identifica tecnologías leyendo `pom.xml` o `build.gradle`
3. Documenta cada endpoint REST con ejemplos de request y response
4. Detecta deuda técnica (métodos largos, TODOs, código comentado)
5. Detecta vulnerabilidades de seguridad (credenciales expuestas, SQL injection)
6. Calcula métricas: líneas de código, cobertura de tests, ratio clases/tests
7. Genera un diagrama de arquitectura en Mermaid
8. Guarda tres reportes Markdown separados por audiencia
9. Activa un modo interactivo para hacer preguntas sobre el proyecto

---

## Requisitos

- Python 3.10 o superior
- Una API key de Anthropic

---

## Instalación

```bash
# Clonar o descargar el proyecto
cd analizador_java

# Instalar dependencias
pip install anthropic pdfplumber

# Configurar la API key (Mac/Linux)
export ANTHROPIC_API_KEY="sk-ant-..."

# Configurar la API key (Windows)
set ANTHROPIC_API_KEY=sk-ant-...
```

---

## Uso

```bash
# Pasando la ruta como argumento
python main.py /ruta/a/tu/proyecto/java

# O dejar que te la pida
python main.py
📁 Ruta del proyecto Java: /ruta/a/tu/proyecto/java
```

### Ejemplo de sesión completa

```
============================================================
  Analizador de Proyectos Java — V3 Profesional
  Proyecto: mi-api-spring
============================================================

[10:32:01] 🚀 INICIO — Proyecto: mi-api-spring
[10:32:01] 🔧 HERRAMIENTA — escanear_proyecto | ruta=/apps/mi-api
[10:32:02] 💭 DECISIÓN — Proyecto escaneado: 47 clases Java, 5 controllers, 12 services
[10:32:02] 🤖 IA — Claude API | Propósito: análisis y generación de reporte
[10:32:03] 📄 LEÍDO — /apps/mi-api/pom.xml | 89 líneas
[10:32:04] 📄 LEÍDO — /apps/mi-api/src/.../ClienteController.java | 203 líneas
[10:32:05] ⚡ CACHÉ — /apps/mi-api/src/.../PagoController.java
...
[10:32:18] 📊 REPORTE — reporte_ejecutivo.md | Guardado en: reportes/reporte_ejecutivo.md
[10:32:24] 📊 REPORTE — reporte_tecnico.md   | Guardado en: reportes/reporte_tecnico.md
[10:32:31] 📊 REPORTE — reporte_apis.md      | Guardado en: reportes/reporte_apis.md

============================================================
  ✅ Análisis completado
============================================================
  📄 reportes/reporte_ejecutivo.md
  📄 reportes/reporte_tecnico.md
  📄 reportes/reporte_apis.md
  📋 reportes/analisis_20250422_103201.log
============================================================

¿Quieres hacer preguntas sobre el proyecto? (s/n): s

💬 Modo interactivo activado.
🧑 Tú: ¿Qué endpoints no tienen pruebas?
🤖 Claude: Los endpoints sin cobertura de test son...
```

---

## Reportes generados

Todos los reportes se guardan en la carpeta `reportes/`.

### `reporte_ejecutivo.md` — para gerencia

Explica en lenguaje simple qué hace el sistema, sus funcionalidades principales, integraciones con sistemas externos y riesgos detectados. Sin tecnicismos.

### `reporte_tecnico.md` — para el equipo de desarrollo

Incluye el stack tecnológico con versiones, el diagrama de arquitectura en Mermaid, métricas detalladas, deuda técnica por archivo con números de línea, vulnerabilidades de seguridad detectadas y casos de prueba sugeridos.

### `reporte_apis.md` — para todos

Documenta cada endpoint REST con método HTTP, ruta, descripción, tabla de parámetros, ejemplo de request JSON, ejemplo de response exitoso y de error, y mínimo 4 casos de prueba por endpoint.

---

## Estructura del proyecto

```
analizador_java/
├── main.py           ← agente principal, loop y modo interactivo
├── herramientas.py   ← 9 herramientas de análisis (escaneo, seguridad, métricas...)
├── cache.py          ← caché por hash MD5, evita reprocesar archivos sin cambios
├── logger.py         ← registro de análisis en consola y archivo .log
├── reportes/         ← carpeta de salida (se crea automáticamente)
└── README.md         ← este archivo
```

---

## Herramientas del agente

El agente decide cuándo usar cada herramienta. Python las ejecuta; Claude las interpreta.

| Herramienta | Qué hace | Usa IA |
|---|---|---|
| `escanear_proyecto` | Mapea estructura, clasifica Controllers/Services/Repos | No |
| `leer_archivo` | Lee `.java`, `pom.xml`, `.yml` con soporte de caché | No |
| `buscar_archivos` | Busca por anotación o texto dentro de archivos | No |
| `analizar_deuda_tecnica` | Detecta métodos largos, TODOs, código comentado | No |
| `analizar_seguridad` | Detecta credenciales expuestas, SQL injection, endpoints sin auth | No |
| `analizar_cobertura_tests` | Compara clases de producción vs archivos de test | No |
| `calcular_metricas` | Cuenta líneas, clases, endpoints, ratio de tests | No |
| `generar_diagrama_mermaid` | Infiere relaciones y genera diagrama de arquitectura | No |
| `guardar_reporte` | Escribe el Markdown final con el análisis de Claude | Sí |

---

## Sistema de caché

El caché evita reprocesar archivos que no cambiaron entre ejecuciones. Se guarda en `.analizador_cache.json` en la carpeta donde corres el script.

```bash
# Ver cuántos archivos están en caché
python -c "from cache import estadisticas_cache; print(estadisticas_cache())"

# Limpiar el caché para forzar análisis completo
python -c "from cache import limpiar_cache; limpiar_cache()"
```

---

## Proyectos compatibles

| Tipo de proyecto | Compatibilidad |
|---|---|
| Spring Boot (2.x, 3.x) | ✅ Completo |
| Spring MVC | ✅ Completo |
| Quarkus | ✅ Parcial (detecta JAX-RS) |
| Micronaut | ✅ Parcial |
| Maven multi-módulo | ✅ Analiza todos los módulos |
| Gradle | ✅ Lee `build.gradle` |
| Proyectos sin framework | ⚠️ Análisis estructural básico |

---

## Limitaciones conocidas

- Proyectos con lógica en stored procedures no se documentan con precisión en el reporte ejecutivo
- PDFs de documentación no se procesan (solo código fuente)
- El diagrama Mermaid infiere relaciones por nombre de clase; puede omitir dependencias inyectadas dinámicamente
- Proyectos de más de 500 clases se analizan por muestreo (Controllers completos, Services representativos)

---

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `ANTHROPIC_API_KEY` | Sí | API key de Anthropic para Claude |

---

## Costo aproximado por análisis

| Tamaño del proyecto | Llamadas a IA | Costo aprox. |
|---|---|---|
| Pequeño (< 20 clases) | 4–6 | ~$0.02 USD |
| Mediano (20–100 clases) | 6–10 | ~$0.05 USD |
| Grande (100+ clases) | 8–15 | ~$0.10 USD |
| Segunda ejecución (con caché) | 2–4 | ~$0.01 USD |

---

## Dependencias

```
anthropic>=0.25.0    # SDK oficial de Anthropic para Claude
pdfplumber>=0.10.0   # Extracción de texto de PDFs (opcional)
```

Todas las demás librerías (`os`, `re`, `json`, `hashlib`, `pathlib`, `logging`) son parte de la librería estándar de Python — no requieren instalación.
