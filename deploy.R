# ==============================================================================
# SCRIPT DE DEPLOYMENT A SHINYAPPS.IO - SteelCheck
# ==============================================================================
# 
# Uso:
#   1. Abrir este archivo en RStudio
#   2. Ejecutar línea por línea (o todo con Ctrl+Shift+Enter)
#   3. Seguir las instrucciones
#
# ==============================================================================

cat("
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║            DEPLOYMENT STEELCHECK → SHINYAPPS.IO              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
\n")

# ==============================================================================
# PASO 1: VERIFICAR E INSTALAR PAQUETES
# ==============================================================================

cat("\n[1/9] Verificando paquetes necesarios...\n")

paquetes_necesarios <- c("rsconnect", "reticulate", "shiny", "bslib", 
                         "plotly", "shinycssloaders")

paquetes_faltantes <- paquetes_necesarios[
  !(paquetes_necesarios %in% installed.packages()[,"Package"])
]

if(length(paquetes_faltantes) > 0) {
  cat("  → Instalando paquetes faltantes:", paste(paquetes_faltantes, collapse=", "), "\n")
  install.packages(paquetes_faltantes)
} else {
  cat("  ✓ Todos los paquetes están instalados\n")
}

# Cargar rsconnect
library(rsconnect)

# ==============================================================================
# PASO 2: VERIFICAR CONFIGURACIÓN DE CUENTA
# ==============================================================================

cat("\n[2/9] Verificando configuración de shinyapps.io...\n")

cuentas <- rsconnect::accounts()

if(nrow(cuentas) == 0) {
  cat("  ✗ No hay cuentas configuradas\n")
  cat("\n  ACCIÓN REQUERIDA:\n")
  cat("  1. Ir a https://www.shinyapps.io/admin/#/tokens\n")
  cat("  2. Click en 'Show' y luego 'Show secret'\n")
  cat("  3. Copiar el comando rsconnect::setAccountInfo(...)\n")
  cat("  4. Ejecutarlo en la consola de R\n")
  cat("  5. Volver a ejecutar este script\n\n")
  stop("Configuración de cuenta requerida")
} else {
  cat("  ✓ Cuenta configurada:", cuentas$name[1], "\n")
  USUARIO <- cuentas$name[1]
}

# ==============================================================================
# PASO 3: VERIFICAR DIRECTORIO DEL PROYECTO
# ==============================================================================

cat("\n[3/9] Verificando directorio del proyecto...\n")

# Intentar detectar directorio automáticamente
if (rstudioapi::isAvailable()) {
  proyecto_dir <- dirname(rstudioapi::getSourceEditorContext()$path)
  setwd(proyecto_dir)
  cat("  → Directorio detectado:", proyecto_dir, "\n")
} else {
  cat("  → Usando directorio actual:", getwd(), "\n")
}

# Verificar que app.R existe
if (!file.exists("app.R")) {
  cat("  ✗ app.R no encontrado en directorio actual\n")
  cat("\n  ACCIÓN REQUERIDA:\n")
  cat("  1. Navegar al directorio del proyecto en RStudio\n")
  cat("  2. O modificar este script para establecer la ruta correcta\n\n")
  stop("app.R no encontrado")
}

cat("  ✓ app.R encontrado\n")

# ==============================================================================
# PASO 4: VERIFICAR ESTRUCTURA DE ARCHIVOS
# ==============================================================================

cat("\n[4/9] Verificando estructura de archivos...\n")

archivos_requeridos <- c(
  "app.R",
  "python",
  "datos",
  "requirements.txt"
)

archivos_faltantes <- c()
for (archivo in archivos_requeridos) {
  if (file.exists(archivo)) {
    cat("  ✓", archivo, "\n")
  } else {
    cat("  ✗", archivo, "FALTANTE\n")
    archivos_faltantes <- c(archivos_faltantes, archivo)
  }
}

if (length(archivos_faltantes) > 0) {
  cat("\n  ADVERTENCIA: Archivos faltantes detectados\n")
  cat("  Archivos faltantes:", paste(archivos_faltantes, collapse=", "), "\n")
  
  respuesta <- readline(prompt = "\n  ¿Continuar de todos modos? (s/n): ")
  if (tolower(respuesta) != "s") {
    stop("Deployment cancelado por el usuario")
  }
}

# ==============================================================================
# PASO 5: VERIFICAR requirements.txt
# ==============================================================================

cat("\n[5/9] Verificando requirements.txt...\n")

if (file.exists("requirements.txt")) {
  reqs <- readLines("requirements.txt")
  cat("  Dependencias Python encontradas:\n")
  for (req in reqs) {
    cat("    -", req, "\n")
  }
} else {
  cat("  ✗ requirements.txt no encontrado\n")
  cat("  → Creando requirements.txt...\n")
  writeLines(c("numpy==1.24.3", "pandas==2.0.3"), "requirements.txt")
  cat("  ✓ requirements.txt creado\n")
}

# ==============================================================================
# PASO 6: VERIFICAR MÓDULOS PYTHON
# ==============================================================================

cat("\n[6/9] Verificando módulos Python...\n")

carpetas_python <- c(
  "python",
  "python/core",
  "python/resistencia",
  "python/clasificacion"
)

for (carpeta in carpetas_python) {
  init_file <- file.path(carpeta, "__init__.py")
  if (file.exists(init_file)) {
    cat("  ✓", init_file, "\n")
  } else {
    cat("  ✗", init_file, "FALTANTE\n")
    if (dir.exists(carpeta)) {
      cat("    → Creando __init__.py...\n")
      file.create(init_file)
      cat("    ✓ Creado\n")
    }
  }
}

# ==============================================================================
# PASO 7: CONFIGURAR NOMBRE DE LA APP
# ==============================================================================

cat("\n[7/9] Configurando nombre de la aplicación...\n")

NOMBRE_APP <- "steelcheck"
cat("  → Nombre de app:", NOMBRE_APP, "\n")
cat("  → URL será: https://", USUARIO, ".shinyapps.io/", NOMBRE_APP, "/\n", sep="")

cambiar_nombre <- readline(prompt = "\n  ¿Cambiar nombre? (s/n): ")
if (tolower(cambiar_nombre) == "s") {
  NOMBRE_APP <- readline(prompt = "  Ingrese nuevo nombre (solo letras y números): ")
  NOMBRE_APP <- tolower(gsub("[^a-z0-9]", "", NOMBRE_APP))
  cat("  → Nuevo nombre:", NOMBRE_APP, "\n")
}

# ==============================================================================
# PASO 8: CONFIRMAR DEPLOYMENT
# ==============================================================================

cat("\n[8/9] Resumen del deployment:\n")
cat("  ────────────────────────────────────────\n")
cat("  Cuenta:    ", USUARIO, "\n")
cat("  App:       ", NOMBRE_APP, "\n")
cat("  Directorio:", getwd(), "\n")
cat("  URL final: ", paste0("https://", USUARIO, ".shinyapps.io/", NOMBRE_APP, "/"), "\n")
cat("  ────────────────────────────────────────\n")

confirmar <- readline(prompt = "\n  ¿Proceder con deployment? (s/n): ")
if (tolower(confirmar) != "s") {
  stop("Deployment cancelado por el usuario")
}

# ==============================================================================
# PASO 9: EJECUTAR DEPLOYMENT
# ==============================================================================

cat("\n[9/9] Ejecutando deployment...\n")
cat("  → Esto puede tomar 3-10 minutos\n")
cat("  → No cerrar RStudio durante el proceso\n\n")

tryCatch({
  
  rsconnect::deployApp(
    appName = NOMBRE_APP,
    appTitle = "SteelCheck - Verificación de Perfiles de Acero",
    appFiles = c(
      "app.R",
      "python",
      "datos",
      "requirements.txt"
    ),
    appPrimaryDoc = "app.R",
    account = USUARIO,
    launch.browser = TRUE,
    forceUpdate = TRUE,
    logLevel = "verbose"
  )
  
  cat("\n")
  cat("╔══════════════════════════════════════════════════════════════╗\n")
  cat("║                                                              ║\n")
  cat("║                   ✅ DEPLOYMENT EXITOSO                      ║\n")
  cat("║                                                              ║\n")
  cat("╚══════════════════════════════════════════════════════════════╝\n")
  cat("\n")
  cat("URL de la aplicación:\n")
  cat("  → https://", USUARIO, ".shinyapps.io/", NOMBRE_APP, "/\n\n", sep="")
  cat("Gestión de la app:\n")
  cat("  → https://www.shinyapps.io/admin/#/application/", NOMBRE_APP, "\n\n", sep="")
  
}, error = function(e) {
  
  cat("\n")
  cat("╔══════════════════════════════════════════════════════════════╗\n")
  cat("║                                                              ║\n")
  cat("║                    ✗ ERROR EN DEPLOYMENT                     ║\n")
  cat("║                                                              ║\n")
  cat("╚══════════════════════════════════════════════════════════════╝\n")
  cat("\n")
  cat("Error:", conditionMessage(e), "\n\n")
  cat("Posibles soluciones:\n")
  cat("  1. Verificar logs en: https://www.shinyapps.io/admin/#/logs\n")
  cat("  2. Revisar que requirements.txt tenga versiones compatibles\n")
  cat("  3. Verificar que todos los archivos necesarios estén incluidos\n")
  cat("  4. Consultar guía de troubleshooting en DEPLOYMENT_SHINYAPPS.md\n\n")
  
})

cat("\n¡Script de deployment finalizado!\n\n")
