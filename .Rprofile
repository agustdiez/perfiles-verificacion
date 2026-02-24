# ==============================================================================
# .Rprofile — SteelCheck
# Se ejecuta automáticamente ANTES de app.R cada vez que se inicia R
# en esta carpeta (o al correr la app desde RStudio).
#
# Responsabilidades:
#   1. Apuntar reticulate al virtualenv del proyecto
#   2. Crear e instalar el virtualenv si no existe todavía
# ==============================================================================

local({

  # Ruta del virtualenv — carpeta dentro del proyecto
  venv_dir <- file.path(getwd(), "venv")

  # Paquetes Python requeridos
  paquetes_py <- c("pandas", "numpy")

  # ── Crear virtualenv si no existe ──────────────────────────────────────
  if (!dir.exists(venv_dir)) {
    message("[SteelCheck] Creando virtualenv en: ", venv_dir)
    reticulate::virtualenv_create(venv_dir)
    message("[SteelCheck] Instalando paquetes Python: ",
            paste(paquetes_py, collapse = ", "))
    reticulate::virtualenv_install(venv_dir, packages = paquetes_py,
                                   ignore_installed = FALSE)
    message("[SteelCheck] Virtualenv listo.")
  }

  # ── Activar el virtualenv ───────────────────────────────────────────────
  reticulate::use_virtualenv(venv_dir, required = TRUE)
  message("[SteelCheck] Python: ",
          reticulate::py_config()$python)
})
