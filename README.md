# SteelCheck

Verificación de perfiles metálicos según **CIRSOC 301 / AISC 360-10**.
Interfaz Shiny (R) + lógica de cálculo en Python (reticulate).

---

## Estructura del proyecto

```
steelcheck/
├── app.R                          # Entrada de la app Shiny
├── .Rprofile                      # Configura el virtualenv automáticamente
├── requirements.txt               # Dependencias Python
│
├── database/
│   ├── cirsoc-shapes-database.csv
│   └── perfiles_SI.csv
│
└── python/
    ├── core/
    │   ├── gestor_base_datos.py
    │   └── utilidades_perfil.py
    ├── clasificacion/
    │   └── clasificacion_seccion.py
    └── resistencia/
        └── compresion.py
```

---

## Instalación (primera vez)

### 1. Requisitos previos

- R ≥ 4.3
- Python ≥ 3.10 (instalado y en el PATH del sistema)
- Paquetes R:

```r
install.packages(c("shiny", "bslib", "plotly", "reticulate", "shinycssloaders"))
```

### 2. Clonar / descomprimir el proyecto

Colocar todos los archivos en una carpeta. La estructura debe quedar
exactamente como se muestra arriba.

### 3. Correr la app

Abrir `app.R` en RStudio y presionar **Run App**, o desde la consola R:

```r
shiny::runApp("ruta/al/proyecto")
```

La primera vez, `.Rprofile` creará automáticamente el virtualenv `venv/`
e instalará `pandas` y `numpy`. Esto tarda ~1 minuto. Las veces siguientes
arranca directo.

---

## Diagnóstico de problemas comunes

### `ModuleNotFoundError: No module named 'pandas'`

Reticulate no está usando el virtualenv del proyecto.
Verificar que `.Rprofile` esté en la **misma carpeta** que `app.R`
y reiniciar R completamente (no solo la sesión de Shiny).

Para verificar manualmente desde la consola R:

```r
library(reticulate)
use_virtualenv("venv", required = TRUE)
py_config()   # debe mostrar la ruta a venv/
py_run_string("import pandas; print(pandas.__version__)")
```

Si el virtualenv no existe aún, crearlo a mano:

```r
library(reticulate)
virtualenv_create("venv")
virtualenv_install("venv", packages = c("pandas", "numpy"))
```

### `Error: Python no encontrado`

Verificar que Python esté en el PATH del sistema:

```bash
# Windows (cmd o PowerShell)
python --version

# Si no está, instalar desde https://python.org
# y marcar "Add Python to PATH" durante la instalación
```

### La app arranca pero los selectores están vacíos

Los CSV de las bases de datos no están en la carpeta `database/`.
Verificar que existan:
- `database/cirsoc-shapes-database.csv`
- `database/perfiles_SI.csv`

---

## Versiones probadas

| Componente | Versión |
|---|---|
| R | 4.5 |
| reticulate | ≥ 1.35 |
| Python | 3.10 – 3.12 |
| pandas | ≥ 2.0 |
| numpy | ≥ 1.24 |
