# ==============================================================================
# app.R — SteelCheck  v0.5
# Verificacion de perfiles metalicos — CIRSOC 301 / AISC 360-10
# ==============================================================================

library(shiny)
library(bslib)
library(plotly)
library(reticulate)
library(shinycssloaders)

# ==============================================================================
# PYTHON
# ==============================================================================

Sys.setenv(STEELCHECK_ROOT = getwd())

py_run_string("
import sys, os
root = os.environ.get('STEELCHECK_ROOT', os.getcwd())
py_path = os.path.join(root, 'python')
if py_path not in sys.path:
    sys.path.insert(0, py_path)
")

gestor_mod  <- import("core.gestor_base_datos")
comp_mod    <- import("resistencia.compresion")
flex_mod    <- import("resistencia.flexion")
interac_mod <- import("resistencia.interaccion")
serv_mod    <- import("servicio.serviciabilidad")
util_mod    <- import("core.utilidades_perfil")

db_manager <- gestor_mod$GestorBaseDatos()
py$`_db_manager` <- db_manager

# ==============================================================================
# HELPERS R
# ==============================================================================

L_PUNTOS <- seq(100, 14000, by = 100)

KL_maximo <- function(Lx, Ly, Lz, Kx, Ky, Kz) max(Kx*Lx, Ky*Ly, Kz*Lz)

generar_curva_Pd <- function(perfil_nombre, tipo_perfil, Fy, Kx, Ky, Kz) {
  message(sprintf("[DEBUG generar_curva_Pd] nombre='%s', tipo='%s'", perfil_nombre, tipo_perfil))
  Pd_vec <- numeric(length(L_PUNTOS))
  for (i in seq_along(L_PUNTOS)) {
    tryCatch({
      res <- comp_mod$compresion(
        perfil_nombre=perfil_nombre, tipo_perfil=tipo_perfil, Fy=Fy,
        Lx=L_PUNTOS[i], Ly=L_PUNTOS[i], db_manager=db_manager,
        Kx=Kx, Ky=Ky, Kz=Kz, mostrar_calculo=FALSE
      )
      Pd_vec[i] <- res$Pd
    }, error = function(e) { 
      message(sprintf("[ERROR generar_curva_Pd] L=%d: %s", L_PUNTOS[i], conditionMessage(e)))
      Pd_vec[i] <<- NA_real_ 
    })
  }
  result <- data.frame(L_m = L_PUNTOS / 1000, Pd = Pd_vec, perfil = perfil_nombre)
  message(sprintf("[DEBUG generar_curva_Pd] Resultado: %d puntos, rango Pd: %.1f - %.1f", 
                 nrow(result), min(Pd_vec, na.rm=TRUE), max(Pd_vec, na.rm=TRUE)))
  return(result)
}

calcular_Pd_punto <- function(perfil_nombre, tipo_perfil, Fy, L_mm, Kx, Ky, Kz) {
  tryCatch({
    message(sprintf("[DEBUG calcular_Pd_punto] nombre='%s', tipo='%s', L=%d", 
                   perfil_nombre, tipo_perfil, L_mm))
    res <- comp_mod$compresion(
      perfil_nombre=perfil_nombre, tipo_perfil=tipo_perfil, Fy=Fy,
      Lx=L_mm, Ly=L_mm, db_manager=db_manager,
      Kx=Kx, Ky=Ky, Kz=Kz, mostrar_calculo=FALSE
    )
    message(sprintf("[DEBUG calcular_Pd_punto] Resultado: Pd=%.1f kN", res$Pd))
    list(Pd=res$Pd, Fcr=res$Fcr, Fe=res$Fe,
         modo=res$modo_pandeo, clase=res$clase_seccion,
         esbeltez=res$esbeltez_max, advertencias=res$advertencias)
  }, error = function(e) {
    message(sprintf("[ERROR calcular_Pd_punto] %s", conditionMessage(e)))
    list(Pd=NA_real_, error=conditionMessage(e))
  })
}

generar_curva_Md <- function(perfil_nombre, tipo_perfil, Fy) {
  Md_vec <- numeric(length(L_PUNTOS))
  for (i in seq_along(L_PUNTOS)) {
    tryCatch({
      res <- flex_mod$flexion(
        perfil_nombre=perfil_nombre, tipo_perfil=tipo_perfil, Fy=Fy,
        Lb=L_PUNTOS[i], db_manager=db_manager,
        Cb=1.0, mostrar_calculo=FALSE
      )
      Md_vec[i] <- res$Md
    }, error = function(e) { Md_vec[i] <<- NA_real_ })
  }
  data.frame(Lb_m = L_PUNTOS / 1000, Md = Md_vec, perfil = perfil_nombre)
}

calcular_Md_punto <- function(perfil_nombre, tipo_perfil, Fy, Lb_mm) {
  tryCatch({
    res <- flex_mod$flexion(
      perfil_nombre=perfil_nombre, tipo_perfil=tipo_perfil, Fy=Fy,
      Lb=Lb_mm, db_manager=db_manager,
      Cb=1.0, mostrar_calculo=FALSE
    )
    list(Md=res$Md, Mn=res$Mn, Mp=res$Mp,
         Lp=res$Lp, Lr=res$Lr,
         modo=res$modo, advertencias=res$advertencias)
  }, error = function(e) list(Md=NA_real_, error=conditionMessage(e)))
}

calcular_interaccion <- function(perfil_nombre, tipo_perfil, Fy, L_mm, Lb_mm, Nu, Mu, Kx, Ky, Kz) {
  tryCatch({
    py$`_ia_p`    <- perfil_nombre
    py$`_ia_tipo` <- tipo_perfil
    py$`_ia_Fy`   <- Fy
    py$`_ia_Lm`   <- L_mm
    py$`_ia_Lb`   <- Lb_mm
    py$`_ia_Nu`   <- Nu
    py$`_ia_Mu`   <- Mu
    py$`_ia_Kx`   <- Kx
    py$`_ia_Ky`   <- Ky
    py$`_ia_Kz`   <- Kz
    py_run_string("
from resistencia.interaccion import interaccion as _fn_ia
_res_ia = _fn_ia(
    perfil_nombre=_ia_p, tipo_perfil=_ia_tipo, Fy=_ia_Fy,
    Lx=_ia_Lm, Ly=_ia_Lm, Lb=_ia_Lb,
    db_manager=_db_manager,
    Nu=_ia_Nu, Mu=_ia_Mu,
    Kx=_ia_Kx, Ky=_ia_Ky, Kz=_ia_Kz,
    mostrar_calculo=False
)
")
    py$`_res_ia`
  }, error = function(e) {
    message("[interaccion] '", perfil_nombre, "': ", conditionMessage(e))
    NULL
  })
}

calcular_serviciabilidad <- function(perfil_nombre, tipo_perfil, L_mm, esquema, fracciones = NULL) {
  tryCatch({
    py$`_sv_p`    <- perfil_nombre
    py$`_sv_tipo` <- tipo_perfil
    py$`_sv_L`    <- L_mm
    py$`_sv_esq`  <- esquema
    if (!is.null(fracciones))
      py$`_sv_fracs` <- as.list(as.integer(fracciones))
    extra <- if (!is.null(fracciones)) ", fracciones=_sv_fracs" else ""
    py_run_string(paste0(
      "from servicio.serviciabilidad import serviciabilidad as _fn_sv\n",
      "_res_sv = _fn_sv(_sv_p, tipo_perfil=_sv_tipo, L=_sv_L, db_manager=_db_manager, esquema=_sv_esq",
      extra, ")\n"
    ))
    py$`_res_sv`
  }, error = function(e) {
    message("[serv] '", perfil_nombre, "': ", conditionMessage(e))
    NULL
  })
}

obtener_props_display <- function(perfil_nombre, tipo = NULL) {
  tryCatch({
    py$`_req_perfil` <- perfil_nombre
    py$`_req_tipo`   <- if(is.null(tipo)) NULL else tipo
    py$`_req_bd`     <- db_manager$nombre_base_activa()
    py_run_string("
from core.utilidades_perfil import extraer_propiedades, formatear_para_display
_perfil_serie = _db_manager.obtener_datos_perfil(_req_perfil, tipo=_req_tipo)
_props        = extraer_propiedades(_perfil_serie, base_datos=_req_bd)
_props_disp   = formatear_para_display(_props, decimales=2)
")
    py$`_props_disp`
  }, error = function(e) {
    message("[props] ERROR '", perfil_nombre, "': ", conditionMessage(e))
    NULL
  })
}

render_props_seccion <- function(datos, unidades, titulo) {
  if (is.null(datos) || length(datos) == 0) return(NULL)
  filas <- mapply(function(clave, valor) {
    ud <- if (!is.null(unidades[[clave]])) unidades[[clave]] else "-"
    if (is.null(valor) || (length(valor) == 1 && is.na(valor))) return(NULL)
    tags$tr(
      tags$td(style="color:#64748b;padding:4px 12px 4px 0;white-space:nowrap;font-weight:500;", clave),
      tags$td(style="color:#0f172a;padding:4px 8px;text-align:right;font-weight:600;",
              format(valor, nsmall=2)),
      tags$td(style="color:#94a3b8;padding:4px 0 4px 8px;font-size:11px;", ud)
    )
  }, names(datos), datos, SIMPLIFY=FALSE)
  filas <- Filter(Negate(is.null), filas)
  if (length(filas) == 0) return(NULL)
  tagList(
    tags$tr(tags$td(colspan="3",
      style="color:#ef4444;font-size:10px;letter-spacing:1.2px;text-transform:uppercase;
             padding:12px 0 6px;border-bottom:2px solid #f1f5f9;font-weight:700;",
      titulo)),
    filas
  )
}

# ==============================================================================
# UI
# ==============================================================================

ui <- page_fluid(
  theme = bs_theme(
    bg="#ffffff", fg="#0f172a", primary="#ef4444", secondary="#3b82f6",
    base_font=font_google("Inter"), code_font=font_google("JetBrains Mono"),
    heading_font=font_google("Outfit")
  ),

  tags$head(tags$style(HTML("
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    body { 
      background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
      font-family: 'Inter', sans-serif;
    }
    
    .card-modern {
      background: white;
      border: none;
      border-radius: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.04);
      padding: 24px;
      height: 100%;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .card-modern:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 6px rgba(0,0,0,0.07), 0 12px 24px rgba(0,0,0,0.08);
    }
    
    .card-title {
      font-family: 'Outfit', sans-serif;
      font-size: 15px;
      font-weight: 700;
      color: #0f172a;
      letter-spacing: -0.02em;
      margin-bottom: 18px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    
    .card-badge {
      width: 28px;
      height: 28px;
      border-radius: 8px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: 700;
      color: white;
      flex-shrink: 0;
      font-family: 'Outfit', sans-serif;
    }
    
    .profile-card {
      background: #f8fafc;
      border: 2px solid #e2e8f0;
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 12px;
      transition: all 0.2s;
    }
    
    .profile-card:hover {
      border-color: #cbd5e1;
      background: #f1f5f9;
    }
    
    .profile-header {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .color-indicator {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      display: inline-block;
      border: 2px solid white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .input-row {
      display: flex;
      gap: 8px;
      align-items: flex-end;
    }
    
    .input-familia { width: 38%; flex-shrink: 0; }
    .input-perfil { flex: 1; min-width: 0; }
    .input-btn { flex-shrink: 0; width: 42px; }
    
    .btn-view-props {
      height: 38px;
      width: 42px;
      background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
      border: none !important;
      color: white !important;
      border-radius: 8px;
      font-size: 16px;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      transition: all 0.2s;
      box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
    }
    
    .btn-view-props:hover {
      background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
      transform: scale(1.05);
      box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
    }
    
    .section-divider {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      color: #ef4444;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      margin: 20px 0 12px;
      padding-bottom: 6px;
      border-bottom: 2px solid #fee2e2;
    }
    
    .btn-calculate {
      width: 100%;
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
      border: none !important;
      font-family: 'Outfit', sans-serif !important;
      font-weight: 700 !important;
      font-size: 14px !important;
      letter-spacing: 0.02em;
      padding: 14px !important;
      margin-top: 16px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(239, 68, 68, 0.25);
      transition: all 0.2s;
    }
    
    .btn-calculate:hover {
      background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important;
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(239, 68, 68, 0.35);
    }
    
    .btn-secondary-action {
      width: 100%;
      background: white !important;
      border: 2px solid #e2e8f0 !important;
      color: #64748b !important;
      font-family: 'JetBrains Mono', monospace !important;
      font-size: 12px !important;
      font-weight: 600 !important;
      margin-top: 8px;
      border-radius: 8px;
      padding: 10px !important;
      transition: all 0.2s;
    }
    
    .btn-secondary-action:hover {
      background: #f8fafc !important;
      border-color: #cbd5e1 !important;
      color: #475569 !important;
    }
    
    .alert-box {
      background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
      border: 2px solid #fbbf24;
      border-radius: 10px;
      padding: 12px 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #92400e;
      margin-top: 12px;
      font-weight: 500;
      box-shadow: 0 2px 8px rgba(251, 191, 36, 0.15);
    }
    
    .result-box {
      background: white;
      border: 2px solid #e2e8f0;
      border-left: 4px solid;
      border-radius: 10px;
      padding: 16px;
      margin-top: 12px;
      transition: all 0.2s;
    }
    
    .result-box:hover {
      border-color: #cbd5e1;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    .result-value {
      font-size: 20px;
      font-weight: 700;
      color: #3b82f6;
      font-family: 'Outfit', sans-serif;
    }
    
    .result-label {
      font-size: 10px;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      font-weight: 600;
      margin-bottom: 4px;
    }
    
    .interaction-box {
      background: white;
      border: 2px solid #e2e8f0;
      border-left: 4px solid;
      border-radius: 10px;
      padding: 16px;
      margin-top: 12px;
    }
    
    .ratio-ok {
      font-size: 22px;
      font-weight: 800;
      color: #10b981;
      font-family: 'Outfit', sans-serif;
    }
    
    .ratio-fail {
      font-size: 22px;
      font-weight: 800;
      color: #ef4444;
      font-family: 'Outfit', sans-serif;
    }
    
    .status-badge {
      display: inline-block;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
      font-family: 'JetBrains Mono', monospace;
    }
    
    .status-ok {
      background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
      color: #065f46;
    }
    
    .status-fail {
      background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
      color: #991b1b;
    }
    
    .service-block {
      background: white;
      border: 2px solid #e2e8f0;
      border-left: 4px solid;
      border-radius: 10px;
      padding: 16px;
      margin-top: 14px;
    }
    
    .service-table {
      width: 100%;
      border-collapse: collapse;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      margin-top: 10px;
    }
    
    .service-table th {
      color: #64748b;
      font-size: 10px;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      padding: 8px 10px;
      border-bottom: 2px solid #e2e8f0;
      text-align: right;
      font-weight: 700;
    }
    
    .service-table th:first-child { text-align: left; }
    
    .service-table td {
      padding: 8px 10px;
      border-bottom: 1px solid #f1f5f9;
      text-align: right;
      font-weight: 500;
    }
    
    .service-table td:first-child {
      color: #64748b;
      text-align: left;
      font-weight: 600;
    }
    
    .service-table tr:hover td {
      background: #f8fafc;
    }
    
    .form-control, .form-select {
      background: white !important;
      border: 2px solid #e2e8f0 !important;
      border-radius: 8px !important;
      color: #0f172a !important;
      font-family: 'Inter', sans-serif !important;
      font-size: 13px !important;
      padding: 8px 12px !important;
      transition: all 0.2s;
      font-weight: 500 !important;
    }
    
    .form-control:focus, .form-select:focus {
      border-color: #3b82f6 !important;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }
    
    label {
      color: #64748b !important;
      font-size: 12px !important;
      font-weight: 600 !important;
      margin-bottom: 6px !important;
    }
    
    .app-header {
      background: white;
      border-radius: 16px;
      padding: 28px 32px;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 8px 24px rgba(0,0,0,0.06);
      display: flex;
      align-items: center;
      gap: 20px;
      border-bottom: 4px solid #ef4444;
    }
    
    .app-title {
      font-family: 'Outfit', sans-serif;
      font-size: 36px;
      font-weight: 800;
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.03em;
    }
    
    .app-subtitle {
      font-size: 13px;
      color: #64748b;
      font-weight: 500;
      font-family: 'JetBrains Mono', monospace;
    }
    
    .version-tag {
      margin-left: auto;
      font-size: 12px;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      color: #3b82f6;
      background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
      padding: 8px 16px;
      border-radius: 20px;
      border: 2px solid #3b82f6;
    }
    
    .info-chip {
      display: inline-block;
      background: #f1f5f9;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 11px;
      font-family: 'JetBrains Mono', monospace;
      color: #475569;
      font-weight: 600;
      margin-right: 6px;
      margin-bottom: 6px;
    }
    
    .modal-content {
      background: white !important;
      border: none !important;
      border-radius: 16px !important;
      box-shadow: 0 20px 60px rgba(0,0,0,0.15) !important;
    }
    
    .modal-header {
      border-bottom: 2px solid #f1f5f9 !important;
      padding: 24px !important;
    }
    
    .modal-title {
      font-family: 'Outfit', sans-serif !important;
      font-size: 18px !important;
      font-weight: 700 !important;
      color: #0f172a !important;
    }
    
    .modal-body {
      padding: 24px !important;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
    }
    
    .props-table {
      width: 100%;
      border-collapse: collapse;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
    }
    
    .props-badge {
      display: inline-block;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      padding: 6px 12px;
      border-radius: 6px;
      text-transform: uppercase;
      margin-bottom: 16px;
    }
    
    .radio-inline input[type='radio'] {
      margin-right: 6px;
    }
    
    .radio-inline label {
      margin-right: 16px;
      font-weight: 600 !important;
    }
    
    ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    
    ::-webkit-scrollbar-track {
      background: #f1f5f9;
      border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
      background: #cbd5e1;
      border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
      background: #94a3b8;
    }
  "))),

  # Header
  div(class="app-header",
    div(
      div(class="app-title", "SteelCheck"),
      div(class="app-subtitle", "Verificación de perfiles metálicos — CIRSOC 301 / AISC 360-10")
    ),
    div(class="version-tag", "v0.5")
  ),

  # Layout principal
  layout_columns(col_widths = c(4, 4, 4),

    # Panel 1 - Compresión
    div(class="card-modern",
      div(class="card-title",
        tags$span(class="card-badge", style="background:linear-gradient(135deg,#ef4444,#dc2626);", "1"),
        "Compresión — Pd vs L [m]"
      ),
      withSpinner(plotlyOutput("plot_Pd", height="340px"), 
                  color="#ef4444", type=4, size=0.7),
      uiOutput("resultado_Pd")
    ),

    # Panel 2 - Flexión
    div(class="card-modern",
      div(class="card-title",
        tags$span(class="card-badge", style="background:linear-gradient(135deg,#3b82f6,#2563eb);", "2"),
        "Flexión — Md vs Lb [m]"
      ),
      withSpinner(plotlyOutput("plot_Md", height="340px"), 
                  color="#3b82f6", type=4, size=0.7),
      uiOutput("resultado_Md")
    ),

    # Panel 3 - Parámetros
    div(class="card-modern", style="overflow-y:auto; max-height:780px;",
      div(class="card-title",
        tags$span(class="card-badge", style="background:linear-gradient(135deg,#64748b,#475569);", "⚙"),
        "Parámetros de Cálculo"
      ),

      div(class="section-divider", "Base de Datos"),
      radioButtons("db_activa", label=NULL,
        choices=c("CIRSOC"="CIRSOC","AISC"="AISC"),
        selected="CIRSOC", inline=TRUE),
      uiOutput("info_db"),

      div(class="section-divider", "Perfiles a Comparar"),

      # Perfil 1
      div(class="profile-card",
        div(class="profile-header",
          tags$span(class="color-indicator", style="background:#ef4444"), "PERFIL 1"
        ),
        div(class="input-row",
          div(class="input-familia",  selectInput("fam1",  "Familia", choices=NULL, width="100%")),
          div(class="input-perfil", selectInput("perf1", "Perfil",  choices=NULL, width="100%")),
          div(class="input-btn",  actionButton("btn_props1", "=", class="btn-view-props", title="Ver propiedades"))
        )
      ),

      # Perfil 2
      div(class="profile-card",
        div(class="profile-header",
          tags$span(class="color-indicator", style="background:#3b82f6"),
          "PERFIL 2  ", tags$small("(opcional)", style="color:#94a3b8")
        ),
        checkboxInput("usar_p2", "Activar perfil 2", FALSE),
        conditionalPanel("input.usar_p2",
          div(class="input-row",
            div(class="input-familia",  selectInput("fam2",  "Familia", choices=NULL, width="100%")),
            div(class="input-perfil", selectInput("perf2", "Perfil",  choices=NULL, width="100%")),
            div(class="input-btn",  actionButton("btn_props2", "=", class="btn-view-props"))
          )
        )
      ),

      # Perfil 3
      div(class="profile-card",
        div(class="profile-header",
          tags$span(class="color-indicator", style="background:#10b981"),
          "PERFIL 3  ", tags$small("(opcional)", style="color:#94a3b8")
        ),
        checkboxInput("usar_p3", "Activar perfil 3", FALSE),
        conditionalPanel("input.usar_p3",
          div(class="input-row",
            div(class="input-familia",  selectInput("fam3",  "Familia", choices=NULL, width="100%")),
            div(class="input-perfil", selectInput("perf3", "Perfil",  choices=NULL, width="100%")),
            div(class="input-btn",  actionButton("btn_props3", "=", class="btn-view-props"))
          )
        )
      ),

      div(class="section-divider", "Propiedades del Acero"),
      numericInput("Fy", "Fy [MPa]", value=235, min=100, max=700, width="100%"),

      div(class="section-divider", "Longitudes de Pandeo"),
      fluidRow(
        column(4, numericInput("Kx", "Kx", value=1.0, min=0.1, max=2.0, step=0.1, width="100%")),
        column(4, numericInput("Ky", "Ky", value=1.0, min=0.1, max=2.0, step=0.1, width="100%")),
        column(4, numericInput("Kz", "Kz", value=1.0, min=0.1, max=2.0, step=0.1, width="100%"))
      ),

      div(class="section-divider", "Puntos de Análisis"),
      numericInput("L_punto", "L adoptada [m]", value=3.0, min=0.1, max=14, step=0.1, width="100%"),
      numericInput("Lb_punto", "Lb flexión [m]", value=3.0, min=0.1, max=14, step=0.1, width="100%"),

      div(class="section-divider", "Cargas (Interacción H1-1)"),
      numericInput("Nu", "Nu [kN]", value=0, min=0, width="100%"),
      numericInput("Mu", "Mu [kN·m]", value=0, min=0, width="100%"),

      actionButton("btn_graficar", "CALCULAR Y GRAFICAR", class="btn-calculate"),
      downloadButton("btn_exportar", "📄 Exportar TXT", class="btn-secondary-action"),
      actionButton("btn_latex", "📐 Ver LaTeX", class="btn-secondary-action")
    )
  ),

  # Fila inferior
  layout_columns(col_widths = c(6, 6), row_heights = c(1, 1),

    # Panel 4 - Interacción
    div(class="card-modern",
      div(class="card-title",
        tags$span(class="card-badge", style="background:linear-gradient(135deg,#8b5cf6,#7c3aed);", "4"),
        "Interacción H1-1 (Nu + Mu)"
      ),
      uiOutput("resultado_interaccion")
    ),

    # Panel 5 - Serviciabilidad
    div(class="card-modern",
      div(class="card-title",
        tags$span(class="card-badge", style="background:linear-gradient(135deg,#10b981,#059669);", "5"),
        "Serviciabilidad — Deformaciones"
      ),
      fluidRow(
        column(6, selectInput("sv_esquema", "Esquema",
          choices=c("Cantilever"="CANTILEVER",
                    "Apoyo Simple"="SIMPLEMENTE_APOYADA",
                    "Empotrada"="EMPOTRADA"),
          selected="SIMPLEMENTE_APOYADA", width="100%")),
        column(6, numericInput("sv_L", "Luz [m]", value=6.0, min=0.5, max=20, step=0.5, width="100%"))
      ),
      uiOutput("tabla_serviciabilidad")
    ),

    # Panel 6 - Info de base de datos (span 2 cols para layout)
    div(class="card-modern",
      div(class="card-title",
        tags$span(class="card-badge", style="background:linear-gradient(135deg,#f59e0b,#d97706);", "ℹ"),
        "Información"
      ),
      tags$div(style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#64748b;line-height:2;",
        tags$p(style="margin:0;",
          tags$b(style="color:#0f172a;", "Normativas:"), tags$br(),
          tags$span("CIRSOC 301:2005 / AISC 360-10")
        ),
        tags$p(style="margin:16px 0 0;",
          tags$b(style="color:#0f172a;", "Factores de resistencia:"), tags$br(),
          tags$span("φ", tags$sub("c"), " = 0.90  |  φ", tags$sub("b"), " = 0.90  |  C", tags$sub("b"), " = 1.0")
        ),
        tags$p(style="margin:16px 0 0;",
          tags$b(style="color:#0f172a;", "Familias soportadas:"), tags$br(),
          tags$span(class="info-chip", "Doble T"),
          tags$span(class="info-chip", "Canales"),
          tags$span(class="info-chip", "Angulares"),
          tags$span(class="info-chip", "Perfiles T"),
          tags$span(class="info-chip", "Tubos Circulares"),
          tags$span(class="info-chip", "Tubos Cuadrados"),
          tags$span(class="info-chip", "Tubos Rectangulares")
        )
      )
    )
  )
)


# ==============================================================================
# SERVER
# ==============================================================================

server <- function(input, output, session) {

  # Actualizar familias cuando cambia la base de datos
  observeEvent(input$db_activa, {
    db_manager$cambiar_base(input$db_activa)
    fams <- db_manager$obtener_familias()
    for (id in c("fam1","fam2","fam3"))
      updateSelectInput(session, id, choices=fams, selected=if(length(fams)>0) fams[1] else NULL)
  })

  # Actualizar perfiles cuando cambia la familia
  observe({
    req(input$fam1)
    p <- db_manager$obtener_perfiles_por_familia(input$fam1)
    updateSelectInput(session, "perf1", choices=p, selected=if(length(p)>0) p[1] else NULL)
  })
  observe({
    req(input$fam2, input$usar_p2)
    p <- db_manager$obtener_perfiles_por_familia(input$fam2)
    updateSelectInput(session, "perf2", choices=p, selected=if(length(p)>0) p[1] else NULL)
  })
  observe({
    req(input$fam3, input$usar_p3)
    p <- db_manager$obtener_perfiles_por_familia(input$fam3)
    updateSelectInput(session, "perf3", choices=p, selected=if(length(p)>0) p[1] else NULL)
  })

  # Inicializar familias al cargar
  observe({
    fams <- tryCatch(db_manager$obtener_familias(), error=function(e) character(0))
    if (length(fams) > 0)
      for (id in c("fam1","fam2","fam3"))
        updateSelectInput(session, id, choices=fams, selected=fams[1])
  })

  # Info de base de datos
  output$info_db <- renderUI({
    s <- tryCatch(db_manager$estadisticas(), error=function(e) NULL)
    div(style="margin-top:12px;",
      if (!is.null(s)) tagList(
        tags$span(class="info-chip", paste0("📊 ", s$total_perfiles, " perfiles")),
        tags$span(class="info-chip", paste0("📁 ", s$familias, " familias")),
        tags$span(class="info-chip", paste0("⚖️  ", round(s$peso_min,1), "-", round(s$peso_max,1), " kg/m")),
        tags$span(class="info-chip", paste0("📏 ", round(s$altura_min,0), "-", round(s$altura_max,0), " mm"))
      ) else tags$span(class="info-chip", "Cargando...")
    )
  })

  # Modal de propiedades
  modal_propiedades <- function(perfil_nombre, tipo_familia, color) {
    props <- obtener_props_display(perfil_nombre, tipo = tipo_familia)
    if (is.null(props)) {
      showModal(modalDialog(
        title = paste("Propiedades —", perfil_nombre),
        "Error al cargar propiedades del perfil.",
        easyClose = TRUE, footer = modalButton("Cerrar")
      ))
      return(NULL)
    }

    familia <- props$familia
    tipo    <- props$tipo
    
    # Mapeo de colores por familia
    badge_color <- switch(familia,
      DOBLE_T = "#3b82f6",
      CANAL = "#10b981",
      ANGULAR = "#ef4444",
      PERFIL_T = "#8b5cf6",
      TUBO_CIRC = "#f59e0b",
      TUBO_CUAD = "#06b6d4",
      TUBO_RECT = "#ec4899",
      "#64748b"
    )
    
    modal_titulo <- paste0(perfil_nombre, "  —  ", tipo)

    showModal(modalDialog(
      title = modal_titulo, size = "l", easyClose = TRUE,
      footer = modalButton("Cerrar"),
      div(style="max-height:500px;overflow-y:auto;",
        tags$span(class="props-badge", 
                  style=paste0("background:",badge_color,";color:white;"), 
                  familia),
        tags$table(class="props-table",
          render_props_seccion(props$basicas, props$basicas_uds, "PROPIEDADES BÁSICAS"),
          render_props_seccion(props$flexion, props$flexion_uds, "FLEXIÓN"),
          render_props_seccion(props$torsion, props$torsion_uds, "TORSIÓN"),
          render_props_seccion(props$seccion, props$seccion_uds, "RELACIONES DE ESBELTEZ"),
          render_props_seccion(props$centro_corte, props$centro_corte_uds, "CENTRO DE CORTE")
        )
      )
    ))
  }

  observeEvent(input$btn_props1, { req(input$perf1, input$fam1); modal_propiedades(input$perf1, input$fam1, "#ef4444") })
  observeEvent(input$btn_props2, { req(input$usar_p2, input$perf2, input$fam2); modal_propiedades(input$perf2, input$fam2, "#3b82f6") })
  observeEvent(input$btn_props3, { req(input$usar_p3, input$perf3, input$fam3); modal_propiedades(input$perf3, input$fam3, "#10b981") })

  # Modal LaTeX
  observeEvent(input$btn_latex, {
    req(datos_grafico())
    d <- datos_grafico()
    L_mm <- input$L_punto * 1000
    
    latex_all <- c()
    for (pt in d$pt_pd) {
      if (is.null(pt)) next
      tryCatch({
        res <- comp_mod$compresion(
          perfil_nombre=pt$nombre, tipo_perfil=pt$tipo, Fy=input$Fy,
          Lx=L_mm, Ly=L_mm, db_manager=db_manager,
          Kx=input$Kx, Ky=input$Ky, Kz=input$Kz,
          mostrar_calculo=FALSE
        )
        if (!is.null(res$latex)) {
          latex_all <- c(latex_all,
            paste0("% ========================================"),
            paste0("% Perfil: ", pt$tipo, " ", pt$nombre),
            paste0("% ========================================"),
            "", res$latex, "", ""
          )
        }
      }, error = function(e) {
        latex_all <<- c(latex_all, paste("% Error en", pt$nombre, ":", conditionMessage(e)), "")
      })
    }
    
    if (length(latex_all) == 0) {
      latex_texto <- "% No hay documentación LaTeX disponible."
    } else {
      latex_texto <- paste(latex_all, collapse="\n")
    }
    
    showModal(modalDialog(
      title = "Documentación LaTeX — Compresión",
      size = "l", easyClose = TRUE,
      footer = tagList(
        tags$button(
          type="button", class="btn btn-secondary btn-sm",
          style="font-family:'JetBrains Mono',monospace;",
          onclick="navigator.clipboard.writeText(document.getElementById('latex_output').innerText);",
          "📋 Copiar"
        ),
        modalButton("Cerrar")
      ),
      tags$pre(
        id="latex_output",
        style="background:#f8fafc;color:#0f172a;padding:16px;border:2px solid #e2e8f0;
               border-radius:10px;font-family:'JetBrains Mono',monospace;font-size:11px;
               max-height:500px;overflow-y:auto;white-space:pre-wrap;",
        latex_texto
      )
    ))
  })

  # Cálculo principal
  datos_grafico <- eventReactive(input$btn_graficar, {
    req(input$perf1, input$fam1, input$Fy, input$L_punto, input$Lb_punto)
    L_mm  <- input$L_punto * 1000
    Lb_mm <- input$Lb_punto * 1000
    Nu    <- input$Nu
    Mu    <- input$Mu

    perfiles <- list(
      list(nombre=input$perf1, tipo=input$fam1, color="#ef4444")
    )
    if (isTRUE(input$usar_p2) && nchar(input$perf2) > 0 && !is.null(input$fam2))
      perfiles[[2]] <- list(nombre=input$perf2, tipo=input$fam2, color="#3b82f6")
    if (isTRUE(input$usar_p3) && nchar(input$perf3) > 0 && !is.null(input$fam3))
      perfiles[[3]] <- list(nombre=input$perf3, tipo=input$fam3, color="#10b981")

    withProgress(message='Calculando curvas...', value=0, {
      n <- length(perfiles)
      curvas_Pd <- list()
      curvas_Md <- list()
      puntos_Pd <- list()
      puntos_Md <- list()
      ints      <- list()
      
      for (i in seq_along(perfiles)) {
        message(sprintf("[DEBUG loop] Perfil %d: nombre='%s', tipo='%s', color='%s'", 
                       i, perfiles[[i]]$nombre, perfiles[[i]]$tipo, perfiles[[i]]$color))
        
        incProgress(1/(n*2), detail=paste("Compresión", perfiles[[i]]$nombre))
        curvas_Pd[[i]] <- generar_curva_Pd(perfiles[[i]]$nombre, perfiles[[i]]$tipo, input$Fy, input$Kx, input$Ky, input$Kz)
        puntos_Pd[[i]] <- calcular_Pd_punto(perfiles[[i]]$nombre, perfiles[[i]]$tipo, input$Fy, L_mm, input$Kx, input$Ky, input$Kz)
        puntos_Pd[[i]]$nombre <- perfiles[[i]]$nombre
        puntos_Pd[[i]]$tipo   <- perfiles[[i]]$tipo
        puntos_Pd[[i]]$color  <- perfiles[[i]]$color

        incProgress(1/(n*2), detail=paste("Flexión", perfiles[[i]]$nombre))
        curvas_Md[[i]] <- generar_curva_Md(perfiles[[i]]$nombre, perfiles[[i]]$tipo, input$Fy)
        puntos_Md[[i]] <- calcular_Md_punto(perfiles[[i]]$nombre, perfiles[[i]]$tipo, input$Fy, Lb_mm)
        puntos_Md[[i]]$nombre <- perfiles[[i]]$nombre
        puntos_Md[[i]]$tipo   <- perfiles[[i]]$tipo
        puntos_Md[[i]]$color  <- perfiles[[i]]$color

        if (Nu > 0 || Mu > 0) {
          ints[[i]] <- calcular_interaccion(
            perfiles[[i]]$nombre, perfiles[[i]]$tipo, input$Fy, L_mm, Lb_mm, Nu, Mu,
            input$Kx, input$Ky, input$Kz
          )
        } else {
          ints[[i]] <- NULL
        }
      }
      list(
        curvas_pd = curvas_Pd, curvas_md = curvas_Md,
        pt_pd = puntos_Pd, pt_md = puntos_Md, ints = ints
      )
    })
  })

  # Gráfico de compresión
  output$plot_Pd <- renderPlotly({
    req(datos_grafico())
    d <- datos_grafico()
    p <- plot_ly()
    for (i in seq_along(d$curvas_pd)) {
      df <- d$curvas_pd[[i]]
      pt <- d$pt_pd[[i]]
      p <- p %>%
        add_trace(data=df, x=~L_m, y=~Pd, type='scatter', mode='lines',
                  name=pt$nombre, line=list(color=pt$color, width=3),
                  hovertemplate=paste0("<b>",pt$nombre,"</b><br>",
                    "L: %{x:.2f} m<br>Pd: %{y:.1f} kN<extra></extra>")) %>%
        add_trace(x=input$L_punto, y=pt$Pd, type='scatter', mode='markers',
                  name=paste0(pt$nombre," @ ",input$L_punto,"m"),
                  marker=list(size=10, color=pt$color, symbol='circle',
                    line=list(color='white', width=2)),
                  hovertemplate=paste0("<b>",pt$nombre,"</b><br>",
                    "L: ",input$L_punto," m<br>Pd: ",round(pt$Pd,1)," kN<extra></extra>"))
    }
    p %>% layout(
      xaxis=list(title="L [m]", gridcolor='#f1f5f9', zeroline=FALSE),
      yaxis=list(title="Pd [kN]", gridcolor='#f1f5f9', zeroline=FALSE),
      plot_bgcolor='white', paper_bgcolor='white',
      font=list(family='Inter', size=11, color='#64748b'),
      showlegend=TRUE, legend=list(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#e2e8f0', borderwidth=1),
      hovermode='closest',
      margin=list(l=60, r=20, t=20, b=50)
    )
  })

  # Gráfico de flexión
  output$plot_Md <- renderPlotly({
    req(datos_grafico())
    d <- datos_grafico()
    p <- plot_ly()
    for (i in seq_along(d$curvas_md)) {
      df <- d$curvas_md[[i]]
      pt <- d$pt_md[[i]]
      p <- p %>%
        add_trace(data=df, x=~Lb_m, y=~Md, type='scatter', mode='lines',
                  name=pt$nombre, line=list(color=pt$color, width=3),
                  hovertemplate=paste0("<b>",pt$nombre,"</b><br>",
                    "Lb: %{x:.2f} m<br>Md: %{y:.1f} kN·m<extra></extra>")) %>%
        add_trace(x=input$Lb_punto, y=pt$Md, type='scatter', mode='markers',
                  name=paste0(pt$nombre," @ ",input$Lb_punto,"m"),
                  marker=list(size=10, color=pt$color, symbol='circle',
                    line=list(color='white', width=2)),
                  hovertemplate=paste0("<b>",pt$nombre,"</b><br>",
                    "Lb: ",input$Lb_punto," m<br>Md: ",round(pt$Md,1)," kN·m<extra></extra>"))
    }
    p %>% layout(
      xaxis=list(title="Lb [m]", gridcolor='#f1f5f9', zeroline=FALSE),
      yaxis=list(title="Md [kN·m]", gridcolor='#f1f5f9', zeroline=FALSE),
      plot_bgcolor='white', paper_bgcolor='white',
      font=list(family='Inter', size=11, color='#64748b'),
      showlegend=TRUE, legend=list(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#e2e8f0', borderwidth=1),
      hovermode='closest',
      margin=list(l=60, r=20, t=20, b=50)
    )
  })

  # Resultados de compresión
  output$resultado_Pd <- renderUI({
    req(datos_grafico())
    d <- datos_grafico()
    tagList(lapply(d$pt_pd, function(pt) {
      if (is.null(pt) || is.na(pt$Pd)) return(NULL)
      adv <- if (length(pt$advertencias) > 0)
        div(class="alert-box", paste(unlist(pt$advertencias), collapse=" | "))
      div(class="result-box", style=paste0("border-left-color:",pt$color,";"),
        fluidRow(
          column(6,
            tags$b(style=paste0("color:",pt$color,";font-family:'Outfit',sans-serif;font-size:13px;font-weight:700;"), pt$nombre),
            tags$br(),
            tags$span(style="color:#94a3b8;font-size:11px;", paste0(pt$modo," • ",pt$clase))
          ),
          column(3,
            div(class="result-label", "Fcr [MPa]"),
            div(class="result-value", style="font-size:14px;", round(pt$Fcr,1))
          ),
          column(3,
            div(class="result-label", "Pd [kN]"),
            div(class="result-value", round(pt$Pd,1))
          )
        ),
        adv
      )
    }))
  })

  # Resultados de flexión
  output$resultado_Md <- renderUI({
    req(datos_grafico())
    d <- datos_grafico()
    tagList(lapply(d$pt_md, function(pt) {
      if (is.null(pt) || is.na(pt$Md)) return(NULL)
      adv <- if (length(pt$advertencias) > 0)
        div(class="alert-box", paste(unlist(pt$advertencias), collapse=" | "))
      div(class="result-box", style=paste0("border-left-color:",pt$color,";"),
        fluidRow(
          column(6,
            tags$b(style=paste0("color:",pt$color,";font-family:'Outfit',sans-serif;font-size:13px;font-weight:700;"), pt$nombre),
            tags$br(),
            tags$span(style="color:#94a3b8;font-size:11px;", pt$modo)
          ),
          column(3,
            div(class="result-label", "Mp [kN·m]"),
            div(class="result-value", style="font-size:14px;", round(pt$Mp,1))
          ),
          column(3,
            div(class="result-label", "Md [kN·m]"),
            div(class="result-value", round(pt$Md,1))
          )
        ),
        adv
      )
    }))
  })

  # Resultados de interacción
  output$resultado_interaccion <- renderUI({
    req(datos_grafico())
    d <- datos_grafico()
    if (length(d$ints) == 0 || all(sapply(d$ints, is.null))) {
      return(div(
        style="padding:40px;text-align:center;color:#94a3b8;font-size:13px;",
        "💡 Ingresá Nu y/o Mu para verificar la ecuación de interacción H1-1"
      ))
    }
    tagList(lapply(seq_along(d$ints), function(i) {
      ri <- d$ints[[i]]
      if (is.null(ri)) return(NULL)
      color <- switch(i, "#ef4444", "#3b82f6", "#10b981")
      ratio <- ri$ratio
      cumple <- isTRUE(ri$cumple)
      cls_ratio <- if (cumple) "ratio-ok" else "ratio-fail"
      status_cls <- if (cumple) "status-ok" else "status-fail"
      etiqueta <- if (cumple) "✓ CUMPLE" else "✗ NO CUMPLE"
      adv <- if (length(ri$advertencias) > 0)
        div(class="alert-box", style="margin-top:10px;",
            paste(unlist(ri$advertencias), collapse=" | "))
      div(class="interaction-box", style=paste0("border-left-color:",color,";"),
        fluidRow(column(12,
          tags$b(style=paste0("color:",color,";font-family:'Outfit',sans-serif;font-size:13px;font-weight:700;"), ri$perfil),
          tags$span(style="color:#94a3b8;font-size:11px;margin-left:10px;",
            paste0(ri$tipo, " — ", ri$ecuacion))
        )),
        tags$hr(style="border-color:#e2e8f0;margin:10px 0;"),
        fluidRow(
          column(3, div(class="result-label","Nu/Pd"), 
                 div(style="color:#64748b;font-size:15px;font-weight:700;", round(ri$Nu_Pd,3))),
          column(3, div(class="result-label","Mu/Md"), 
                 div(style="color:#64748b;font-size:15px;font-weight:700;", round(ri$Mu_Md,3))),
          column(3, div(class="result-label","Ratio"), 
                 div(class=cls_ratio, round(ratio,3))),
          column(3, div(class="result-label","Estado"),
            div(class=paste("status-badge", status_cls), etiqueta))
        ),
        tags$hr(style="border-color:#e2e8f0;margin:10px 0;"),
        fluidRow(
          column(4, div(class="result-label","Pd [kN]"), 
                 div(style="color:#94a3b8;font-size:12px;font-weight:600;", round(ri$Pd,1))),
          column(4, div(class="result-label","Md [kN·m]"), 
                 div(style="color:#94a3b8;font-size:12px;font-weight:600;", round(ri$Md,1))),
          column(4, div(class="result-label","KL/r"), 
                 div(style="color:#94a3b8;font-size:12px;font-weight:600;", round(ri$esbeltez_max,1)))
        ),
        adv
      )
    }))
  })

  # Tabla de serviciabilidad
  output$tabla_serviciabilidad <- renderUI({
    req(input$perf1, input$sv_esquema, input$sv_L)

    L_mm <- input$sv_L * 1000
    esquema <- input$sv_esquema
    fracs <- if (esquema == "CANTILEVER")
               list(50L, 100L, 120L, 150L, 200L)
             else
               list(100L, 200L, 300L, 400L, 500L)

    perfiles <- list(list(nombre=input$perf1, tipo=input$fam1, color="#ef4444"))
    if (isTRUE(input$usar_p2) && nchar(input$perf2) > 0)
      perfiles[[2]] <- list(nombre=input$perf2, tipo=input$fam2, color="#3b82f6")
    if (isTRUE(input$usar_p3) && nchar(input$perf3) > 0)
      perfiles[[3]] <- list(nombre=input$perf3, tipo=input$fam3, color="#10b981")

    tagList(lapply(perfiles, function(p) {
      res <- calcular_serviciabilidad(p$nombre, p$tipo, L_mm, esquema, fracs)
      if (is.null(res))
        return(div(class="alert-box", paste("Error calculando", p$nombre)))

      tabla <- res$tabla
      if (is.null(tabla) || length(tabla) == 0)
        return(div(class="alert-box", paste("Sin datos para", p$nombre)))

      div(class="service-block", style=paste0("border-left-color:", p$color, ";"),
        div(style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;",
          tags$span(style=paste0("color:",p$color,";font-family:'Outfit',sans-serif;font-size:13px;font-weight:700;"), p$nombre),
          tags$span(style="color:#94a3b8;font-size:11px;font-family:'JetBrains Mono',monospace;",
            paste0("Ix=", res$Ix_cm4, " cm⁴  |  Iy=", res$Iy_cm4, " cm⁴"))
        ),
        tags$table(class="service-table",
          tags$thead(
            tags$tr(
              tags$th(style="text-align:left;", "δ adm"),
              tags$th("δ [mm]"),
              tags$th(colspan="2", style="color:#3b82f6;text-align:center;border-bottom:2px solid #3b82f6;", "EJE FUERTE"),
              tags$th(colspan="2", style="color:#10b981;text-align:center;border-bottom:2px solid #10b981;", "EJE DÉBIL")
            ),
            tags$tr(
              tags$th(""), tags$th(""),
              tags$th(style="color:#3b82f6;", "P [kN]"),
              tags$th(style="color:#3b82f6;", "q [kN/m]"),
              tags$th(style="color:#10b981;", "P [kN]"),
              tags$th(style="color:#10b981;", "q [kN/m]")
            )
          ),
          tags$tbody(
            lapply(tabla, function(f) {
              tags$tr(
                tags$td(f$fraccion),
                tags$td(sprintf("%.1f", f$delta_mm)),
                tags$td(style="color:#3b82f6;font-weight:600;", sprintf("%.1f", f$Px_kN)),
                tags$td(style="color:#3b82f6;font-weight:600;", sprintf("%.2f", f$qx_kNm)),
                tags$td(style="color:#10b981;font-weight:600;", sprintf("%.1f", f$Py_kN)),
                tags$td(style="color:#10b981;font-weight:600;", sprintf("%.2f", f$qy_kNm))
              )
            })
          )
        ),
        if (length(res$advertencias) > 0)
          div(class="alert-box", style="margin-top:10px;",
              paste(unlist(res$advertencias), collapse=" | "))
      )
    }))
  })

  # Exportar resultados
  output$btn_exportar <- downloadHandler(
    filename = function() paste0("steelcheck_", format(Sys.time(), "%Y%m%d_%H%M"), ".txt"),
    content = function(file) {
      req(datos_grafico())
      d <- datos_grafico()
      L_mm <- input$L_punto * 1000
      Lb_mm <- input$Lb_punto * 1000
      lineas <- c(
        "STEELCHECK v0.5 — Reporte de Cálculo Detallado",
        strrep("=", 70),
        paste0("Fecha y hora: ", Sys.time()),
        paste0("Base de datos: ", input$db_activa),
        "",
        "PARÁMETROS DE CÁLCULO",
        strrep("-", 70),
        paste0("Acero: Fy = ", input$Fy, " MPa"),
        paste0("Factores de longitud efectiva: Kx=", input$Kx, "  Ky=", input$Ky, "  Kz=", input$Kz),
        paste0("Longitud de pandeo: L = ", input$L_punto, " m  (", L_mm, " mm)"),
        paste0("Longitud de pandeo lateral: Lb = ", input$Lb_punto, " m  (", Lb_mm, " mm)"),
        paste0("Cargas actuantes: Nu = ", input$Nu, " kN  |  Mu = ", input$Mu, " kN·m"),
        "", strrep("=", 70), ""
      )
      for (pt in d$pt_pd) {
        if (is.null(pt)) next
        lineas <- c(lineas, "", strrep("*", 70),
                    paste0("PERFIL: ", pt$tipo, " ", pt$nombre), strrep("*", 70), "")
        tryCatch({
          txt <- capture.output(comp_mod$compresion(
            perfil_nombre=pt$nombre, tipo_perfil=pt$tipo, Fy=input$Fy,
            Lx=L_mm, Ly=L_mm, db_manager=db_manager,
            Kx=input$Kx, Ky=input$Ky, Kz=input$Kz, mostrar_calculo=TRUE))
          lineas <- c(lineas, txt, "")
        }, error=function(e) {
          lineas <<- c(lineas, paste("Error en compresión:", conditionMessage(e)), "")
        })
        tryCatch({
          txt <- capture.output(flex_mod$flexion(
            perfil_nombre=pt$nombre, tipo_perfil=pt$tipo, Fy=input$Fy,
            Lb=Lb_mm, db_manager=db_manager, mostrar_calculo=TRUE))
          lineas <- c(lineas, txt, "")
        }, error=function(e) {
          lineas <<- c(lineas, paste("Error en flexión:", conditionMessage(e)), "")
        })
        lineas <- c(lineas, strrep("-", 70), "")
      }
      writeLines(lineas, file)
    }
  )
}

# ==============================================================================
shinyApp(ui=ui, server=server)
