# ==============================================================================
# app.R — SteelCheck  v0.4
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

L_PUNTOS <- seq(100, 14000, by = 100)   # 140 puntos — cada 10 cm

KL_maximo <- function(Lx, Ly, Lz, Kx, Ky, Kz) max(Kx*Lx, Ky*Ly, Kz*Lz)

generar_curva_Pd <- function(perfil_nombre, Fy, Kx, Ky, Kz) {
  Pd_vec <- numeric(length(L_PUNTOS))
  for (i in seq_along(L_PUNTOS)) {
    tryCatch({
      res <- comp_mod$compresion(
        perfil_nombre=perfil_nombre, Fy=Fy,
        Lx=L_PUNTOS[i], Ly=L_PUNTOS[i], db_manager=db_manager,
        Kx=Kx, Ky=Ky, Kz=Kz, mostrar_calculo=FALSE
      )
      Pd_vec[i] <- res$Pd
    }, error = function(e) { Pd_vec[i] <<- NA_real_ })
  }
  data.frame(L_m = L_PUNTOS / 1000, Pd = Pd_vec, perfil = perfil_nombre)
}

calcular_Pd_punto <- function(perfil_nombre, Fy, L_mm, Kx, Ky, Kz) {
  tryCatch({
    res <- comp_mod$compresion(
      perfil_nombre=perfil_nombre, Fy=Fy,
      Lx=L_mm, Ly=L_mm, db_manager=db_manager,
      Kx=Kx, Ky=Ky, Kz=Kz, mostrar_calculo=FALSE
    )
    list(Pd=res$Pd, Fcr=res$Fcr, Fe=res$Fe,
         modo=res$modo_pandeo, clase=res$clase_seccion,
         esbeltez=res$esbeltez_max, advertencias=res$advertencias)
  }, error = function(e) list(Pd=NA_real_, error=conditionMessage(e)))
}

generar_curva_Md <- function(perfil_nombre, Fy) {
  Md_vec <- numeric(length(L_PUNTOS))
  for (i in seq_along(L_PUNTOS)) {
    tryCatch({
      res <- flex_mod$flexion(
        perfil_nombre=perfil_nombre, Fy=Fy,
        Lb=L_PUNTOS[i], db_manager=db_manager,
        Cb=1.0, mostrar_calculo=FALSE
      )
      Md_vec[i] <- res$Md
    }, error = function(e) { Md_vec[i] <<- NA_real_ })
  }
  data.frame(Lb_m = L_PUNTOS / 1000, Md = Md_vec, perfil = perfil_nombre)
}

calcular_Md_punto <- function(perfil_nombre, Fy, Lb_mm) {
  tryCatch({
    res <- flex_mod$flexion(
      perfil_nombre=perfil_nombre, Fy=Fy,
      Lb=Lb_mm, db_manager=db_manager,
      Cb=1.0, mostrar_calculo=FALSE
    )
    list(Md=res$Md, Mn=res$Mn, Mp=res$Mp,
         Lp=res$Lp, Lr=res$Lr,
         modo=res$modo, advertencias=res$advertencias)
  }, error = function(e) list(Md=NA_real_, error=conditionMessage(e)))
}

calcular_interaccion <- function(perfil_nombre, Fy, L_mm, Lb_mm, Nu, Mu, Kx, Ky, Kz) {
  tryCatch({
    py$`_ia_p`  <- perfil_nombre
    py$`_ia_Fy` <- Fy
    py$`_ia_Lm` <- L_mm
    py$`_ia_Lb` <- Lb_mm
    py$`_ia_Nu` <- Nu
    py$`_ia_Mu` <- Mu
    py$`_ia_Kx` <- Kx
    py$`_ia_Ky` <- Ky
    py$`_ia_Kz` <- Kz
    py_run_string("
from resistencia.interaccion import interaccion as _fn_ia
_res_ia = _fn_ia(
    perfil_nombre=_ia_p, Fy=_ia_Fy,
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

calcular_serviciabilidad <- function(perfil_nombre, L_mm, esquema, fracciones = NULL) {
  tryCatch({
    py$`_sv_p`   <- perfil_nombre
    py$`_sv_L`   <- L_mm
    py$`_sv_esq` <- esquema
    if (!is.null(fracciones))
      py$`_sv_fracs` <- as.list(as.integer(fracciones))
    extra <- if (!is.null(fracciones)) ", fracciones=_sv_fracs" else ""
    py_run_string(paste0(
      "from servicio.serviciabilidad import serviciabilidad as _fn_sv\n",
      "_res_sv = _fn_sv(_sv_p, L=_sv_L, db_manager=_db_manager, esquema=_sv_esq",
      extra, ")\n"
    ))
    py$`_res_sv`
  }, error = function(e) {
    message("[serv] '", perfil_nombre, "': ", conditionMessage(e))
    NULL
  })
}

obtener_props_display <- function(perfil_nombre) {
  tryCatch({
    py$`_req_perfil` <- perfil_nombre
    py$`_req_bd`     <- db_manager$nombre_base_activa()
    py_run_string("
from core.utilidades_perfil import extraer_propiedades, formatear_para_display
_perfil_serie = _db_manager.obtener_datos_perfil(_req_perfil)
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
      tags$td(style="color:#94a3b8;padding:3px 8px 3px 0;white-space:nowrap;", clave),
      tags$td(style="color:#e2e8f0;padding:3px 4px;text-align:right;font-weight:600;",
              format(valor, nsmall=2)),
      tags$td(style="color:#475569;padding:3px 0 3px 6px;font-size:10px;", ud)
    )
  }, names(datos), datos, SIMPLIFY=FALSE)
  filas <- Filter(Negate(is.null), filas)
  if (length(filas) == 0) return(NULL)
  tagList(
    tags$tr(tags$td(colspan="3",
      style="color:#e8523a;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;
             padding:10px 0 4px;border-bottom:1px solid #2a2f3f;font-weight:700;",
      titulo)),
    filas
  )
}

# ==============================================================================
# UI
# ==============================================================================

ui <- page_fluid(
  theme = bs_theme(
    bg="#0f1117", fg="#e2e8f0", primary="#e8523a", secondary="#4a9eff",
    base_font=font_google("IBM Plex Sans"), code_font=font_google("IBM Plex Mono")
  ),

  tags$head(tags$style(HTML("
    body { background:#0f1117; }
    .panel-sc {
      background:#171b26; border:1px solid #2a2f3f;
      border-radius:4px; padding:16px; height:100%;
    }
    .panel-title {
      font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:600;
      color:#64748b; letter-spacing:1.5px; text-transform:uppercase;
      margin-bottom:12px; display:flex; align-items:center; gap:8px;
    }
    .num-badge {
      width:18px; height:18px; border-radius:50%;
      display:inline-flex; align-items:center; justify-content:center;
      font-size:10px; font-weight:700; color:white; flex-shrink:0;
    }
    .profile-slot {
      background:#0c0f18; border:1px solid #2a2f3f;
      border-radius:3px; padding:10px; margin-bottom:8px;
    }
    .slot-header {
      font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:600;
      color:#94a3b8; margin-bottom:6px; display:flex; align-items:center; gap:6px;
    }
    .color-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
    .triple-row { display:flex; gap:6px; align-items:flex-end; }
    .triple-fam  { width:36%; flex-shrink:0; }
    .triple-perf { flex:1; min-width:0; }
    .triple-btn  { flex-shrink:0; width:34px; padding-bottom:1px; }
    .btn-props {
      height:34px; width:34px;
      background:#1e2330 !important; border:1px solid #2a2f3f !important;
      color:#4a9eff !important; border-radius:3px; font-size:14px; padding:0;
      display:flex; align-items:center; justify-content:center;
    }
    .btn-props:hover { background:#253047 !important; border-color:#4a9eff !important; }
    .section-sep {
      font-family:'IBM Plex Mono',monospace; font-size:9px; font-weight:600;
      color:#e8523a; letter-spacing:2px; text-transform:uppercase;
      margin:14px 0 8px; padding-bottom:4px; border-bottom:1px solid #2a2f3f;
    }
    .btn-graficar {
      width:100%; background:#e8523a !important; border:none !important;
      font-family:'IBM Plex Mono',monospace !important;
      font-weight:600 !important; letter-spacing:0.5px; margin-top:12px;
    }
    .btn-graficar:hover { background:#c7402a !important; }
    .btn-export {
      width:100%; background:transparent !important;
      border:1px solid #2a2f3f !important; color:#94a3b8 !important;
      font-family:'IBM Plex Mono',monospace !important;
      font-size:11px !important; margin-top:6px;
    }
    .btn-export:hover { 
      background:#1a1f2e !important; 
      border-color:#94a3b8 !important; 
    }
    .btn-latex {
      width:100%; background:transparent !important;
      border:1px solid #2a2f3f !important; color:#3ecf8e !important;
      font-family:'IBM Plex Mono',monospace !important;
      font-size:11px !important; margin-top:6px;
    }
    .btn-latex:hover { 
      background:#1a2f26 !important; 
      border-color:#3ecf8e !important; 
    }
    .advertencia-box {
      background:#1a1206; border:1px solid #f59e0b; border-radius:3px;
      padding:8px 10px; font-family:'IBM Plex Mono',monospace;
      font-size:10px; color:#f59e0b; margin-top:8px;
    }
    .resultado-box {
      background:#0c0f18; border:1px solid #2a2f3f; border-radius:3px;
      padding:10px; font-family:'IBM Plex Mono',monospace;
      font-size:11px; margin-top:8px;
    }
    .resultado-val { font-size:16px; font-weight:600; color:#4a9eff; }
    .int-box {
      background:#0c0f18; border:1px solid #2a2f3f; border-radius:3px;
      padding:10px; font-family:'IBM Plex Mono',monospace;
      font-size:11px; margin-top:8px;
    }
    .int-ratio-ok  { font-size:18px; font-weight:700; color:#3ecf8e; }
    .int-ratio-nok { font-size:18px; font-weight:700; color:#e8523a; }
    .int-label     { font-size:9px; color:#475569; letter-spacing:1px;
                     text-transform:uppercase; margin-bottom:2px; }
    .sv-bloque {
      background:#0c0f18; border:1px solid #2a2f3f; border-radius:3px;
      padding:10px; margin-top:10px;
    }
    .sv-table {
      width:100%; border-collapse:collapse;
      font-family:'IBM Plex Mono',monospace; font-size:10px; margin-top:6px;
    }
    .sv-table th {
      color:#64748b; font-size:9px; letter-spacing:0.8px; text-transform:uppercase;
      padding:4px 6px; border-bottom:1px solid #2a2f3f; text-align:right;
    }
    .sv-table th:first-child { text-align:left; }
    .sv-table td {
      padding:3px 6px; border-bottom:1px solid #1a1d28; text-align:right;
    }
    .sv-table td:first-child { color:#94a3b8; text-align:left; }
    .sv-table tr:hover td { background:#171b26; }
    .form-control, .form-select, .selectize-input {
      background:#0c0f18 !important; border:1px solid #2a2f3f !important;
      color:#e2e8f0 !important;
      font-family:'IBM Plex Mono',monospace !important; font-size:11px !important;
    }
    label { color:#64748b !important; font-size:11px !important; }
    .app-header {
      display:flex; align-items:baseline; gap:12px;
      margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid #2a2f3f;
    }
    .app-title {
      font-family:'IBM Plex Mono',monospace; font-size:20px;
      font-weight:600; color:#e8523a;
    }
    .app-subtitle { font-size:11px; color:#475569; font-family:'IBM Plex Mono',monospace; }
    .version-badge {
      margin-left:auto; font-size:10px; font-family:'IBM Plex Mono',monospace;
      color:#4a9eff; border:1px solid #4a9eff; padding:2px 8px; border-radius:2px;
    }
    .modal-content  { background:#171b26 !important; border:1px solid #2a2f3f !important; }
    .modal-header   { border-bottom:1px solid #2a2f3f !important; padding:12px 16px !important; }
    .modal-title    { font-family:'IBM Plex Mono',monospace !important;
                      font-size:13px !important; color:#e2e8f0 !important; }
    .modal-body     { padding:16px !important; font-family:'IBM Plex Mono',monospace; font-size:11px; }
    .btn-close      { filter:invert(1) !important; }
    .props-table    { width:100%; border-collapse:collapse;
                      font-family:'IBM Plex Mono',monospace; font-size:11px; }
    .props-badge    { display:inline-block; font-size:9px; font-weight:700;
                      letter-spacing:1px; padding:2px 7px; border-radius:2px;
                      text-transform:uppercase; margin-bottom:10px; }
    ::-webkit-scrollbar { width:4px; }
    ::-webkit-scrollbar-track { background:#0f1117; }
    ::-webkit-scrollbar-thumb { background:#2a2f3f; border-radius:2px; }
  "))),

  # Header
  div(class="app-header",
    div(class="app-title", "SteelCheck"),
    div(class="app-subtitle", "Verificacion de perfiles — CIRSOC 301 / AISC 360-10"),
    div(class="version-badge", "v0.4")
  ),

  # Fila superior
  layout_columns(col_widths = c(4, 4, 4),

    div(class="panel-sc",
      div(class="panel-title",
        tags$span(class="num-badge", style="background:#e8523a", "3"),
        "Compresion — Pd vs L [m]"
      ),
      withSpinner(plotlyOutput("plot_Pd", height="360px"), color="#e8523a", type=4, size=0.6),
      uiOutput("resultado_Pd")
    ),

    div(class="panel-sc",
      div(class="panel-title",
        tags$span(class="num-badge", style="background:#4a9eff", "2"),
        "Flexion — Md vs Lb [m]"
      ),
      withSpinner(plotlyOutput("plot_Md", height="360px"), color="#4a9eff", type=4, size=0.6),
      uiOutput("resultado_Md")
    ),

    div(class="panel-sc", style="overflow-y:auto; max-height:820px;",
      div(class="panel-title",
        tags$span(class="num-badge", style="background:#64748b", "1"),
        "Parametros de calculo"
      ),

      div(class="section-sep", "Base de datos"),
      radioButtons("db_activa", label=NULL,
        choices=c("CIRSOC"="CIRSOC","AISC"="AISC"),
        selected="CIRSOC", inline=TRUE),

      div(class="section-sep", "Perfiles"),

      div(class="profile-slot",
        div(class="slot-header",
          tags$span(class="color-dot", style="background:#e8523a"), "PERFIL 1"
        ),
        div(class="triple-row",
          div(class="triple-fam",  selectInput("fam1",  "Familia", choices=NULL, width="100%")),
          div(class="triple-perf", selectInput("perf1", "Perfil",  choices=NULL, width="100%")),
          div(class="triple-btn",  actionButton("btn_props1", "=", class="btn-props", title="Ver propiedades"))
        )
      ),

      div(class="profile-slot",
        div(class="slot-header",
          tags$span(class="color-dot", style="background:#4a9eff"),
          "PERFIL 2  ", tags$small("(opcional)", style="color:#475569")
        ),
        checkboxInput("usar_p2", "Activar perfil 2", FALSE),
        conditionalPanel("input.usar_p2",
          div(class="triple-row",
            div(class="triple-fam",  selectInput("fam2",  "Familia", choices=NULL, width="100%")),
            div(class="triple-perf", selectInput("perf2", "Perfil",  choices=NULL, width="100%")),
            div(class="triple-btn",  actionButton("btn_props2", "=", class="btn-props", title="Ver propiedades"))
          )
        )
      ),

      div(class="profile-slot",
        div(class="slot-header",
          tags$span(class="color-dot", style="background:#3ecf8e"),
          "PERFIL 3  ", tags$small("(opcional)", style="color:#475569")
        ),
        checkboxInput("usar_p3", "Activar perfil 3", FALSE),
        conditionalPanel("input.usar_p3",
          div(class="triple-row",
            div(class="triple-fam",  selectInput("fam3",  "Familia", choices=NULL, width="100%")),
            div(class="triple-perf", selectInput("perf3", "Perfil",  choices=NULL, width="100%")),
            div(class="triple-btn",  actionButton("btn_props3", "=", class="btn-props", title="Ver propiedades"))
          )
        )
      ),

      div(class="section-sep", "Material"),
      fluidRow(
        column(6, numericInput("Fy", "Fy [MPa]", 250, min=100, max=700)),
        column(6, numericInput("E",  "E [MPa]",  200000))
      ),

      div(class="section-sep", "Longitudes efectivas"),
      tags$small(style="color:#475569;font-family:'IBM Plex Mono',monospace;font-size:10px;display:block;margin-bottom:6px;",
        "Punto en curva usa max(Kx*L, Ky*L, Kz*L)"),
      fluidRow(
        column(6, numericInput("Kx", "Kx", 1.0, min=0.1, max=3, step=0.1)),
        column(6, numericInput("Ky", "Ky", 1.0, min=0.1, max=3, step=0.1))
      ),
      fluidRow(
        column(6, numericInput("Kz", "Kz", 1.0, min=0.1, max=3, step=0.1)),
        column(6)
      ),
      fluidRow(
        column(6, numericInput("L_punto",  "L adoptada [m]",  5.0, min=0.1, max=14, step=0.1)),
        column(6, numericInput("Lb_punto", "Lb adoptado [m]", 5.0, min=0.1, max=14, step=0.1))
      ),

      div(class="section-sep", "Verificacion (cargas de diseno)"),
      tags$small(style="color:#475569;font-family:'IBM Plex Mono',monospace;font-size:10px;display:block;margin-bottom:6px;",
        "Dejar en 0 para omitir la verificacion H1-1"),
      fluidRow(
        column(6, numericInput("Nu", "Nu [kN]",    0, min=0, step=10)),
        column(6, numericInput("Mu", "Mu [kN·m]",  0, min=0, step=10))
      ),

      actionButton("btn_graficar", "GRAFICAR", class="btn btn-primary btn-graficar"),
      downloadButton("btn_exportar", "Exportar verbose", class="btn btn-export"),
      actionButton("btn_latex", "Ver LaTeX", class="btn btn-latex")
    )
  ),

  # Fila inferior
  tags$br(),
  layout_columns(col_widths = c(4, 5, 3),

    div(class="panel-sc",
      div(class="panel-title",
        tags$span(class="num-badge", style="background:#3ecf8e", "4"),
        "Verificacion flexocompresion — H1-1"
      ),
      uiOutput("resultado_interaccion")
    ),

    div(class="panel-sc",
      div(class="panel-title",
        tags$span(class="num-badge", style="background:#64748b", "5"),
        "Cargas admisibles por deformacion"
      ),
      fluidRow(
        column(6,
          selectInput("sv_esquema", "Esquema estatico",
            choices = c(
              "Cantilever"          = "CANTILEVER",
              "Simplemente apoyada" = "SIMPLE",
              "Empotrada ambos ext" = "EMPOTRADA"
            ),
            selected = "SIMPLE", width = "100%"
          )
        ),
        column(6,
          numericInput("sv_L", "Longitud [m]", 5.0, min=0.5, max=14, step=0.5, width="100%")
        )
      ),
      uiOutput("tabla_serviciabilidad")
    ),

    div(
      div(class="panel-sc", style="margin-bottom:12px;",
        div(class="panel-title",
          tags$span(class="num-badge", style="background:#64748b", "6"),
          "Info de base de datos"
        ),
        uiOutput("info_db")
      ),
      div(class="panel-sc",
        div(class="panel-title",
          tags$span(class="num-badge", style="background:#64748b", "7"),
          "Referencias"
        ),
        tags$p(
          style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#475569;margin:0;line-height:1.8;",
          "CIRSOC 301:2005 / AISC 360-10", tags$br(),
          "phic = 0.90  |  phib = 0.90  |  Cb = 1.0"
        )
      )
    )
  )
)


# ==============================================================================
# SERVER
# ==============================================================================

server <- function(input, output, session) {

  observeEvent(input$db_activa, {
    db_manager$cambiar_base(input$db_activa)
    fams <- db_manager$obtener_familias()
    for (id in c("fam1","fam2","fam3"))
      updateSelectInput(session, id, choices=fams, selected=fams[1])
  })

  observe({
    req(input$fam1)
    p <- db_manager$obtener_perfiles_por_familia(input$fam1)
    updateSelectInput(session, "perf1", choices=p, selected=p[1])
  })
  observe({
    req(input$fam2, input$usar_p2)
    p <- db_manager$obtener_perfiles_por_familia(input$fam2)
    updateSelectInput(session, "perf2", choices=p, selected=p[1])
  })
  observe({
    req(input$fam3, input$usar_p3)
    p <- db_manager$obtener_perfiles_por_familia(input$fam3)
    updateSelectInput(session, "perf3", choices=p, selected=p[1])
  })

  observe({
    fams <- tryCatch(db_manager$obtener_familias(), error=function(e) character(0))
    if (length(fams) > 0)
      for (id in c("fam1","fam2","fam3"))
        updateSelectInput(session, id, choices=fams, selected=fams[1])
  })

  output$info_db <- renderUI({
    s <- tryCatch(db_manager$estadisticas(), error=function(e) NULL)
    div(style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#64748b;line-height:1.8;",
      tags$b(style="color:#94a3b8;", input$db_activa), tags$br(),
      if (!is.null(s)) tagList(
        paste0("Perfiles: ", s$total_perfiles), tags$br(),
        paste0("Familias: ", s$familias), tags$br(),
        paste0("Peso: ", round(s$peso_min,1), " - ", round(s$peso_max,1), " kg/m"), tags$br(),
        paste0("d: ", round(s$altura_min,0), " - ", round(s$altura_max,0), " mm")
      ) else "Cargando..."
    )
  })

  modal_propiedades <- function(perfil_nombre, color) {
    props <- obtener_props_display(perfil_nombre)
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
    unidades_basicas    <- list(Ag="cm²", d="mm", bf="mm", tw="mm", tf="mm", A="mm", B="mm", e="mm", Peso="kg/m")
    unidades_flexion    <- list(Ix="cm⁴", Iy="cm⁴", Sx="cm³", Sy="cm³", Zx="cm³", Zy="cm³",
                                rx="cm", ry="cm", iv="cm", xp="cm", yp="cm")
    unidades_torsion    <- list(J="cm⁴", Cw="cm⁶", ro="cm")
    unidades_corte      <- list(xo="cm", yo="cm", eo="cm", H="-")
    unidades_clasif     <- list()

    badge_color <- switch(familia, DOBLE_T="#4a9eff", CANAL="#3ecf8e", ANGULAR="#e8523a", "#64748b")
    modal_titulo <- paste0(perfil_nombre, "  —  ", tipo)

    showModal(modalDialog(
      title = modal_titulo, size = "l", easyClose = TRUE,
      footer = modalButton("Cerrar"),
      div(style="max-height:500px;overflow-y:auto;",
        tags$span(class="props-badge", style=paste0("background:",badge_color,";color:white;"), familia),
        tags$table(class="props-table",
          render_props_seccion(props$basicas,       unidades_basicas,    "PROPIEDADES BASICAS"),
          render_props_seccion(props$flexion,       unidades_flexion,    "FLEXION"),
          render_props_seccion(props$torsion,       unidades_torsion,    "TORSION"),
          render_props_seccion(props$centro_corte,  unidades_corte,      "CENTRO DE CORTE"),
          render_props_seccion(props$clasificacion, unidades_clasif,     "CLASIFICACION")
        )
      )
    ))
  }

  observeEvent(input$btn_props1, { modal_propiedades(input$perf1, "#e8523a") })
  observeEvent(input$btn_props2, { req(input$usar_p2); modal_propiedades(input$perf2, "#4a9eff") })
  observeEvent(input$btn_props3, { req(input$usar_p3); modal_propiedades(input$perf3, "#3ecf8e") })

  # Modal LaTeX
  observeEvent(input$btn_latex, {
    req(datos_grafico())
    d    <- datos_grafico()
    L_mm <- input$L_punto * 1000
    
    # Capturar latex de cada perfil
    latex_all <- c()
    for (pt in d$pt_pd) {
      if (is.null(pt)) next
      tryCatch({
        res <- comp_mod$compresion(
          perfil_nombre=pt$nombre, Fy=input$Fy,
          Lx=L_mm, Ly=L_mm, db_manager=db_manager,
          Kx=input$Kx, Ky=input$Ky, Kz=input$Kz, 
          mostrar_calculo=FALSE
        )
        if (!is.null(res$latex)) {
          latex_all <- c(latex_all, 
            paste0("% ========================================"),
            paste0("% Perfil: ", pt$nombre),
            paste0("% ========================================"),
            "",
            res$latex,
            "",
            ""
          )
        }
      }, error = function(e) {
        latex_all <<- c(latex_all, paste("% Error en", pt$nombre, ":", conditionMessage(e)), "")
      })
    }
    
    if (length(latex_all) == 0) {
      latex_texto <- "% No hay documentación LaTeX disponible.\n% Verificá que compresion.py esté generando resultados['latex']."
    } else {
      latex_texto <- paste(latex_all, collapse="\n")
    }
    
    showModal(modalDialog(
      title = "Documentación LaTeX — Compresión",
      size = "l",
      easyClose = TRUE,
      footer = tagList(
        tags$button(
          type="button", class="btn btn-secondary btn-sm",
          style="font-family:'IBM Plex Mono',monospace;",
          onclick="navigator.clipboard.writeText(document.getElementById('latex_output').innerText);",
          "📋 Copiar"
        ),
        modalButton("Cerrar")
      ),
      tags$pre(
        id="latex_output",
        style="background:#0c0f18;color:#94a3b8;padding:12px;border:1px solid #2a2f3f;
               border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;
               max-height:500px;overflow-y:auto;white-space:pre-wrap;",
        latex_texto
      )
    ))
  })

  datos_grafico <- eventReactive(input$btn_graficar, {
    req(input$perf1, input$Fy, input$L_punto, input$Lb_punto)
    L_mm  <- input$L_punto  * 1000
    Lb_mm <- input$Lb_punto * 1000
    Nu    <- input$Nu
    Mu    <- input$Mu

    perfiles <- list(
      list(nombre=input$perf1, color="#e8523a")
    )
    if (isTRUE(input$usar_p2) && nchar(input$perf2) > 0)
      perfiles[[2]] <- list(nombre=input$perf2, color="#4a9eff")
    if (isTRUE(input$usar_p3) && nchar(input$perf3) > 0)
      perfiles[[3]] <- list(nombre=input$perf3, color="#3ecf8e")

    withProgress(message='Graficando curvas...', value=0, {
      n <- length(perfiles)
      curvas_Pd <- list()
      curvas_Md <- list()
      puntos_Pd <- list()
      puntos_Md <- list()
      ints      <- list()
      for (i in seq_along(perfiles)) {
        incProgress(1/(n*2), detail=paste("Compresión", perfiles[[i]]$nombre))
        curvas_Pd[[i]] <- generar_curva_Pd(perfiles[[i]]$nombre, input$Fy, input$Kx, input$Ky, input$Kz)
        puntos_Pd[[i]] <- calcular_Pd_punto(perfiles[[i]]$nombre, input$Fy, L_mm, input$Kx, input$Ky, input$Kz)
        puntos_Pd[[i]]$nombre <- perfiles[[i]]$nombre
        puntos_Pd[[i]]$color  <- perfiles[[i]]$color

        incProgress(1/(n*2), detail=paste("Flexión", perfiles[[i]]$nombre))
        curvas_Md[[i]] <- generar_curva_Md(perfiles[[i]]$nombre, input$Fy)
        puntos_Md[[i]] <- calcular_Md_punto(perfiles[[i]]$nombre, input$Fy, Lb_mm)
        puntos_Md[[i]]$nombre <- perfiles[[i]]$nombre
        puntos_Md[[i]]$color  <- perfiles[[i]]$color

        if (Nu > 0 || Mu > 0) {
          ints[[i]] <- calcular_interaccion(perfiles[[i]]$nombre, input$Fy, L_mm, Lb_mm, Nu, Mu,
                                            input$Kx, input$Ky, input$Kz)
        } else {
          ints[[i]] <- NULL
        }
      }
    })
    list(curvas_pd=curvas_Pd, curvas_md=curvas_Md,
         pt_pd=puntos_Pd, pt_md=puntos_Md, ints=ints)
  })

  output$plot_Pd <- renderPlotly({
    req(datos_grafico())
    d <- datos_grafico()
    p <- plot_ly()
    for (i in seq_along(d$curvas_pd)) {
      c <- d$curvas_pd[[i]]
      pt <- d$pt_pd[[i]]
      p <- p %>%
        add_trace(data=c, x=~L_m, y=~Pd, type='scatter', mode='lines',
                  line=list(color=pt$color, width=2), name=pt$nombre, showlegend=TRUE) %>%
        add_trace(x=input$L_punto, y=pt$Pd, type='scatter', mode='markers',
                  marker=list(color=pt$color, size=8, symbol='circle'),
                  name=paste0(pt$nombre," @ L=",input$L_punto,"m"), showlegend=FALSE)
    }
    p %>%
      layout(
        xaxis=list(title="L [m]", gridcolor='#2a2f3f', zerolinecolor='#2a2f3f'),
        yaxis=list(title="Pd [kN]", gridcolor='#2a2f3f', zerolinecolor='#2a2f3f'),
        paper_bgcolor='#171b26', plot_bgcolor='#0f1117',
        font=list(family='IBM Plex Mono', size=10, color='#94a3b8'),
        legend=list(orientation='h', x=0, y=1.1, font=list(size=9))
      ) %>%
      config(displayModeBar=FALSE)
  })

  output$plot_Md <- renderPlotly({
    req(datos_grafico())
    d <- datos_grafico()
    p <- plot_ly()
    for (i in seq_along(d$curvas_md)) {
      c <- d$curvas_md[[i]]
      pt <- d$pt_md[[i]]
      p <- p %>%
        add_trace(data=c, x=~Lb_m, y=~Md, type='scatter', mode='lines',
                  line=list(color=pt$color, width=2), name=pt$nombre, showlegend=TRUE) %>%
        add_trace(x=input$Lb_punto, y=pt$Md, type='scatter', mode='markers',
                  marker=list(color=pt$color, size=8, symbol='circle'),
                  name=paste0(pt$nombre," @ Lb=",input$Lb_punto,"m"), showlegend=FALSE)
    }
    p %>%
      layout(
        xaxis=list(title="Lb [m]", gridcolor='#2a2f3f', zerolinecolor='#2a2f3f'),
        yaxis=list(title="Md [kN·m]", gridcolor='#2a2f3f', zerolinecolor='#2a2f3f'),
        paper_bgcolor='#171b26', plot_bgcolor='#0f1117',
        font=list(family='IBM Plex Mono', size=10, color='#94a3b8'),
        legend=list(orientation='h', x=0, y=1.1, font=list(size=9))
      ) %>%
      config(displayModeBar=FALSE)
  })

  output$resultado_Pd <- renderUI({
    req(datos_grafico())
    d <- datos_grafico()
    tagList(lapply(d$pt_pd, function(pt) {
      if (is.null(pt) || is.na(pt$Pd)) return(NULL)
      adv <- if (length(pt$advertencias) > 0)
        div(class="advertencia-box", paste(unlist(pt$advertencias), collapse=" | "))
      div(class="resultado-box", style=paste0("border-left:3px solid ",pt$color,";"),
        fluidRow(
          column(6,
            tags$b(style=paste0("color:",pt$color,";font-family:'IBM Plex Mono',monospace;font-size:11px;"), pt$nombre),
            tags$br(),
            tags$span(style="color:#64748b;font-size:10px;", paste0("Modo: ",pt$modo," | Clase: ",pt$clase))
          ),
          column(3,
            div(style="color:#64748b;font-size:10px;", "Fcr"),
            div(class="resultado-val", style="font-size:13px;", paste0(round(pt$Fcr,1)," MPa"))
          ),
          column(3,
            div(style="color:#64748b;font-size:10px;", "Pd"),
            div(class="resultado-val", paste0(round(pt$Pd,1)," kN"))
          )
        ),
        adv
      )
    }))
  })

  output$resultado_Md <- renderUI({
    req(datos_grafico())
    d <- datos_grafico()
    tagList(lapply(d$pt_md, function(pt) {
      if (is.null(pt) || is.na(pt$Md)) return(NULL)
      adv <- if (length(pt$advertencias) > 0)
        div(class="advertencia-box", paste(unlist(pt$advertencias), collapse=" | "))
      div(class="resultado-box", style=paste0("border-left:3px solid ",pt$color,";"),
        fluidRow(
          column(6,
            tags$b(style=paste0("color:",pt$color,";font-family:'IBM Plex Mono',monospace;font-size:11px;"), pt$nombre),
            tags$br(),
            tags$span(style="color:#64748b;font-size:10px;", paste0("Modo: ",pt$modo))
          ),
          column(3,
            div(style="color:#64748b;font-size:10px;", "Mp"),
            div(class="resultado-val", style="font-size:13px;", paste0(round(pt$Mp,1)," kN·m"))
          ),
          column(3,
            div(style="color:#64748b;font-size:10px;", "Md"),
            div(class="resultado-val", paste0(round(pt$Md,1)," kN·m"))
          )
        ),
        adv
      )
    }))
  })

  output$resultado_interaccion <- renderUI({
    req(datos_grafico())
    d <- datos_grafico()
    if (length(d$ints) == 0 || all(sapply(d$ints, is.null))) {
      return(div(
        style="padding:20px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#475569;",
        "Ingresar Nu y/o Mu para verificar H1-1"
      ))
    }
    tagList(lapply(seq_along(d$ints), function(i) {
      ri <- d$ints[[i]]
      if (is.null(ri)) return(NULL)
      color     <- switch(i, "#e8523a", "#4a9eff", "#3ecf8e")
      ratio     <- ri$ratio
      cumple    <- isTRUE(ri$cumple)
      cls_ratio <- if (cumple) "int-ratio-ok" else "int-ratio-nok"
      etiqueta  <- if (cumple) "OK" else "NO CUMPLE"
      adv <- if (length(ri$advertencias) > 0)
        div(class="advertencia-box", paste(unlist(ri$advertencias), collapse=" | "))
      div(class="int-box", style=paste0("border-left:3px solid ",color,";"),
        fluidRow(column(12,
          tags$b(style=paste0("color:",color,";font-family:'IBM Plex Mono',monospace;font-size:11px;"), ri$perfil),
          tags$span(style="color:#475569;font-size:10px;margin-left:8px;",
            paste0("(", ri$tipo, " — ", ri$ecuacion, ")"))
        )),
        tags$hr(style="border-color:#2a2f3f;margin:6px 0;"),
        fluidRow(
          column(3, div(class="int-label","Nu/Pd"), div(style="color:#94a3b8;font-size:13px;font-weight:600;", round(ri$Nu_Pd,3))),
          column(3, div(class="int-label","Mu/Md"), div(style="color:#94a3b8;font-size:13px;font-weight:600;", round(ri$Mu_Md,3))),
          column(3, div(class="int-label","Ratio"), div(class=cls_ratio, round(ratio,3))),
          column(3, div(class="int-label","Estado"),
            div(style=paste0("font-size:11px;font-weight:700;margin-top:2px;",
              if (cumple) "color:#3ecf8e;" else "color:#e8523a;"), etiqueta))
        ),
        tags$hr(style="border-color:#2a2f3f;margin:6px 0;"),
        fluidRow(
          column(4, div(class="int-label","Pd [kN]"), div(style="color:#64748b;font-size:11px;", round(ri$Pd,1))),
          column(4, div(class="int-label","Md [kN·m]"), div(style="color:#64748b;font-size:11px;", round(ri$Md,1))),
          column(4, div(class="int-label","KL/r"), div(style="color:#64748b;font-size:11px;", round(ri$esbeltez_max,1)))
        ),
        adv
      )
    }))
  })

  # Panel 5 — Serviciabilidad
  output$tabla_serviciabilidad <- renderUI({
    req(input$perf1, input$sv_esquema, input$sv_L)

    L_mm    <- input$sv_L * 1000
    esquema <- input$sv_esquema
    fracs   <- if (esquema == "CANTILEVER")
                 list(50L, 100L, 120L, 150L, 200L)
               else
                 list(100L, 200L, 300L, 400L, 500L)

    perfiles <- list(list(nombre=input$perf1, color="#e8523a"))
    if (isTRUE(input$usar_p2) && nchar(input$perf2) > 0)
      perfiles[[2]] <- list(nombre=input$perf2, color="#4a9eff")
    if (isTRUE(input$usar_p3) && nchar(input$perf3) > 0)
      perfiles[[3]] <- list(nombre=input$perf3, color="#3ecf8e")

    tagList(lapply(perfiles, function(p) {
      res <- calcular_serviciabilidad(p$nombre, L_mm, esquema, fracs)
      if (is.null(res))
        return(div(class="advertencia-box", paste("Error calculando", p$nombre)))

      tabla <- res$tabla
      if (is.null(tabla) || length(tabla) == 0)
        return(div(class="advertencia-box", paste("Sin datos para", p$nombre)))

      div(class="sv-bloque",
        style=paste0("border-left:3px solid ", p$color, ";"),
        div(style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;",
          tags$span(style=paste0("color:",p$color,";font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:700;"), p$nombre),
          tags$span(style="color:#475569;font-size:10px;font-family:'IBM Plex Mono',monospace;",
            paste0("Ix=", res$Ix_cm4, " cm4  |  Iy=", res$Iy_cm4, " cm4"))
        ),
        tags$table(class="sv-table",
          tags$thead(
            tags$tr(
              tags$th(style="text-align:left;", "d adm"),
              tags$th("d [mm]"),
              tags$th(colspan="2", style="color:#4a9eff;text-align:center;border-bottom:1px solid #4a9eff44;", "EJE FUERTE"),
              tags$th(colspan="2", style="color:#3ecf8e;text-align:center;border-bottom:1px solid #3ecf8e44;", "EJE DEBIL")
            ),
            tags$tr(
              tags$th(""), tags$th(""),
              tags$th(style="color:#4a9eff;", "P [kN]"),
              tags$th(style="color:#4a9eff;", "q [kN/m]"),
              tags$th(style="color:#3ecf8e;", "P [kN]"),
              tags$th(style="color:#3ecf8e;", "q [kN/m]")
            )
          ),
          tags$tbody(
            lapply(tabla, function(f) {
              tags$tr(
                tags$td(f$fraccion),
                tags$td(sprintf("%.1f", f$delta_mm)),
                tags$td(style="color:#4a9eff;", sprintf("%.1f", f$Px_kN)),
                tags$td(style="color:#4a9eff;", sprintf("%.2f", f$qx_kNm)),
                tags$td(style="color:#3ecf8e;", sprintf("%.1f", f$Py_kN)),
                tags$td(style="color:#3ecf8e;", sprintf("%.2f", f$qy_kNm))
              )
            })
          )
        ),
        if (length(res$advertencias) > 0)
          div(class="advertencia-box", style="margin-top:6px;",
              paste(unlist(res$advertencias), collapse=" | "))
      )
    }))
  })

  output$btn_exportar <- downloadHandler(
    filename = function() paste0("steelcheck_", format(Sys.time(), "%Y%m%d_%H%M"), ".txt"),
    content = function(file) {
      req(datos_grafico())
      d    <- datos_grafico()
      L_mm  <- input$L_punto  * 1000
      Lb_mm <- input$Lb_punto * 1000
      lineas <- c(
        "STEELCHECK — Verbose de calculo",
        paste0("Generado: ", Sys.time()),
        paste0("Base de datos: ", input$db_activa),
        paste0("Fy = ", input$Fy, " MPa"),
        paste0("Kx = ", input$Kx, "  Ky = ", input$Ky, "  Kz = ", input$Kz),
        paste0("L adoptada = ", input$L_punto, " m  |  Lb = ", input$Lb_punto, " m"),
        paste0("Nu = ", input$Nu, " kN  |  Mu = ", input$Mu, " kN*m"),
        strrep("=", 70), ""
      )
      for (pt in d$pt_pd) {
        if (is.null(pt)) next
        tryCatch({
          txt <- capture.output(comp_mod$compresion(
            perfil_nombre=pt$nombre, Fy=input$Fy,
            Lx=L_mm, Ly=L_mm, db_manager=db_manager,
            Kx=input$Kx, Ky=input$Ky, Kz=input$Kz, mostrar_calculo=TRUE))
          lineas <- c(lineas, txt, "")
        }, error=function(e) {
          lineas <<- c(lineas, paste("Error comp:", conditionMessage(e)), "")
        })
        tryCatch({
          txt <- capture.output(flex_mod$flexion(
            perfil_nombre=pt$nombre, Fy=input$Fy,
            Lb=Lb_mm, db_manager=db_manager, mostrar_calculo=TRUE))
          lineas <- c(lineas, txt, "")
        }, error=function(e) {
          lineas <<- c(lineas, paste("Error flex:", conditionMessage(e)), "")
        })
        lineas <- c(lineas, strrep("-",70), "")
      }
      writeLines(lineas, file)
    }
  )

}

# ==============================================================================
shinyApp(ui=ui, server=server)
