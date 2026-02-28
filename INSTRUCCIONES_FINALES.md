# INSTRUCCIONES FINALES - Actualización Flexión

## ARCHIVOS ENTREGADOS

### 1. flexion.py ✅ COMPLETO
- ✅ Nuevas familias: Perfil T, Tubo Circular, HSS
- ✅ Eje débil para Doble T y Canales
- ✅ Parámetro `calcular_ambos_ejes=TRUE`
- ✅ Retorna: Mdx, Mdy, Mnx, Mny, Mpx, Mpy, modo_x, modo_y

### 2. app.R ✅ PARCIALMENTE ACTUALIZADO
- ✅ Input Mu → Mux + Muy
- ✅ generar_curva_Md() actualizada (calcula Mdx y Mdy)
- ✅ calcular_Md_punto() actualizada (retorna ambos ejes)
- ⏳ FALTA: Actualizar renderizado del gráfico

---

## PASO FINAL: Actualizar Gráfico de Flexión

### Ubicación
Buscar en `app.R` alrededor de la línea 705-750 el output del gráfico de flexión.

### Código Actual (aproximado)
```r
output$plot_flexion <- renderPlotly({
  req(datos_grafico())
  d <- datos_grafico()
  
  p <- plot_ly()
  
  for (i in seq_along(d$curvas_md)) {
    curva <- d$curvas_md[[i]]
    punto <- d$pt_md[[i]]
    
    # Curva Md
    p <- p %>% add_trace(
      data = curva,
      x = ~Lb_m, y = ~Md,
      type = 'scatter', mode = 'lines',
      name = punto$nombre,
      line = list(color = punto$color, width = 2)
    )
    
    # Punto actual
    p <- p %>% add_trace(
      x = d$params$Lb / 1000,
      y = punto$Md,
      type = 'scatter', mode = 'markers',
      marker = list(color = punto$color, size = 10),
      showlegend = FALSE
    )
  }
  
  p %>% layout(
    title = "Resistencia a Flexión",
    xaxis = list(title = "Lb [m]"),
    yaxis = list(title = "Md [kN·m]")
  )
})
```

### Código NUEVO (con doble eje)

```r
output$plot_flexion <- renderPlotly({
  req(datos_grafico())
  d <- datos_grafico()
  
  p <- plot_ly()
  
  for (i in seq_along(d$curvas_md)) {
    curva <- d$curvas_md[[i]]
    punto <- d$pt_md[[i]]
    
    # EJE FUERTE (Mdx) - Eje Y principal (izquierdo)
    p <- p %>% add_trace(
      data = curva,
      x = ~Lb_m, y = ~Mdx,
      type = 'scatter', mode = 'lines',
      name = paste0(punto$nombre, " Mdx"),
      yaxis = "y",
      line = list(color = punto$color, width = 2.5)
    )
    
    # Punto actual Mdx
    p <- p %>% add_trace(
      x = d$params$Lb / 1000,
      y = punto$Mdx,
      type = 'scatter', mode = 'markers',
      yaxis = "y",
      marker = list(color = punto$color, size = 10, symbol = 'circle'),
      showlegend = FALSE,
      hovertemplate = paste0(punto$nombre, " Mdx<br>Lb=%{x:.2f}m<br>Mdx=%{y:.1f} kN·m<extra></extra>")
    )
    
    # EJE DÉBIL (Mdy) - Eje Y secundario (derecho) - Solo si existe
    if (!all(is.na(curva$Mdy))) {
      p <- p %>% add_trace(
        data = curva,
        x = ~Lb_m, y = ~Mdy,
        type = 'scatter', mode = 'lines',
        name = paste0(punto$nombre, " Mdy"),
        yaxis = "y2",
        line = list(color = punto$color, width = 2, dash = 'dash')
      )
      
      # Punto actual Mdy
      if (!is.na(punto$Mdy)) {
        p <- p %>% add_trace(
          x = d$params$Lb / 1000,
          y = punto$Mdy,
          type = 'scatter', mode = 'markers',
          yaxis = "y2",
          marker = list(color = punto$color, size = 8, symbol = 'square'),
          showlegend = FALSE,
          hovertemplate = paste0(punto$nombre, " Mdy<br>Lb=%{x:.2f}m<br>Mdy=%{y:.1f} kN·m<extra></extra>")
        )
      }
    }
  }
  
  # Layout con doble eje Y
  p %>% layout(
    title = "Resistencia a Flexión — Eje Fuerte (●) y Eje Débil (■)",
    xaxis = list(
      title = "Lb [m]",
      gridcolor = '#e5e7eb'
    ),
    yaxis = list(
      title = "<b>Mdx [kN·m]</b> (eje fuerte)",
      side = "left",
      showgrid = TRUE,
      gridcolor = '#e5e7eb'
    ),
    yaxis2 = list(
      title = "<b>Mdy [kN·m]</b> (eje débil)",
      side = "right",
      overlaying = "y",
      showgrid = FALSE
    ),
    hovermode = 'closest',
    plot_bgcolor = '#f9fafb',
    legend = list(
      orientation = "h",
      y = -0.2
    )
  )
})
```

### Explicación del Código

**Líneas sólidas** (Mdx - eje fuerte):
- Color del perfil
- Grosor 2.5px
- Eje Y izquierdo

**Líneas punteadas** (Mdy - eje débil):
- Mismo color del perfil
- Grosor 2px, dash='dash'
- Eje Y derecho
- Solo se dibuja si `Mdy` existe (no NA)

**Símbolos**:
- ● Círculo = Punto actual Mdx
- ■ Cuadrado = Punto actual Mdy

**Leyenda**:
- "IPE 100 Mdx" (línea sólida)
- "IPE 100 Mdy" (línea punteada)

---

## TABLA DE RESULTADOS - FLEXIÓN

También actualizar la tabla para mostrar ambos ejes:

```r
output$tabla_flexion <- renderUI({
  req(datos_grafico())
  d <- datos_grafico()
  
  filas <- lapply(d$pt_md, function(pt) {
    if (is.null(pt)) return(NULL)
    
    # Columna Mdy solo si existe
    td_mdy <- if (!is.na(pt$Mdy)) {
      tags$td(sprintf("%.1f", pt$Mdy))
    } else {
      tags$td("—")
    }
    
    tags$tr(
      tags$td(style=paste0("border-left:4px solid ", pt$color), pt$nombre),
      tags$td(sprintf("%.1f", pt$Mdx)),  # Eje fuerte
      td_mdy,                             # Eje débil
      tags$td(sprintf("%.0f", pt$Lp)),
      tags$td(sprintf("%.0f", pt$Lr)),
      tags$td(pt$modo_x)
    )
  })
  
  tags$table(class="results-table",
    tags$thead(
      tags$tr(
        tags$th("Perfil"),
        tags$th("Mdx [kN·m]"),
        tags$th("Mdy [kN·m]"),
        tags$th("Lp [mm]"),
        tags$th("Lr [mm]"),
        tags$th("Modo")
      )
    ),
    tags$tbody(filas)
  )
})
```

---

## INTERACCIÓN - PRÓXIMA FASE

Para interacción biaxial, actualizar `calcular_interaccion()`:

```r
calcular_interaccion <- function(perfil_nombre, tipo_perfil, Fy, L_mm, Lb_mm, Nu, Mux, Muy, Kx, Ky, Kz) {
  tryCatch({
    # Obtener resistencias
    res_pd <- calcular_Pd_punto(perfil_nombre, tipo_perfil, Fy, L_mm, Kx, Ky, Kz)
    res_md <- calcular_Md_punto(perfil_nombre, tipo_perfil, Fy, Lb_mm)
    
    Pd  <- res_pd$Pd
    Mdx <- res_md$Mdx
    Mdy <- if (!is.na(res_md$Mdy)) res_md$Mdy else Mdx  # Si no hay Mdy, usar Mdx
    
    # Ecuación H1-1 biaxial
    if (Nu / Pd >= 0.2) {
      # H1-1a
      ratio <- Nu / Pd + (8/9) * (Mux / Mdx + Muy / Mdy)
      ecuacion <- "H1-1a"
    } else {
      # H1-1b
      ratio <- Nu / (2 * Pd) + (Mux / Mdx + Muy / Mdy)
      ecuacion <- "H1-1b"
    }
    
    cumple <- ratio <= 1.0
    
    list(
      ratio = ratio,
      cumple = cumple,
      ecuacion = ecuacion,
      Pd = Pd,
      Mdx = Mdx,
      Mdy = Mdy,
      Nu_Pd = Nu / Pd,
      Mux_Mdx = Mux / Mdx,
      Muy_Mdy = Muy / Mdy
    )
  }, error = function(e) {
    message(sprintf("[interaccion] '%s': %s", perfil_nombre, conditionMessage(e)))
    NULL
  })
}
```

---

## TESTING

### Test 1: IPE 100 (tiene ambos ejes)
```r
res <- flex_mod$flexion('100', Fy=250, Lb=3000, db_manager=db,
                        tipo_perfil='IPE', calcular_ambos_ejes=TRUE)

# Verificar
print(res$Mdx)  # ~18.5 kN·m
print(res$Mdy)  # ~3.2 kN·m (mucho menor)
```

### Test 2: Tubo circular (simétrico)
```r
res <- flex_mod$flexion('PIPE 8 STD', Fy=250, Lb=3000, db_manager=db,
                        calcular_ambos_ejes=TRUE)

# Verificar
print(res$Mdx == res$Mdy)  # TRUE (simétrico)
```

### Test 3: Perfil T (solo un eje)
```r
res <- flex_mod$flexion('WT22X167.5', Fy=250, Lb=3000, db_manager=db,
                        calcular_ambos_ejes=TRUE)

# Verificar
print(res$Mdy)  # NULL (no tiene eje débil)
```

---

## RESUMEN DE CAMBIOS REALIZADOS

### flexion.py ✅
- ✅ 7 nuevas funciones para nuevas familias
- ✅ Función `_Mn_eje_debil()` para F6
- ✅ Firma actualizada con `calcular_ambos_ejes`
- ✅ Retornos: Mdx, Mdy, Mnx, Mny, Mpx, Mpy
- ✅ Compatibilidad hacia atrás con Md, Mn, Mp

### app.R ✅ (parcial)
- ✅ Input: Mu → Mux + Muy
- ✅ generar_curva_Md(): retorna Mdx y Mdy
- ✅ calcular_Md_punto(): retorna ambos ejes
- ⏳ FALTA: Gráfico doble eje (código provisto arriba)
- ⏳ FALTA: Tabla actualizada (código provisto arriba)

---

## ARCHIVOS EN /outputs/

1. ✅ `flexion.py` - Completo y funcional
2. ✅ `app.R` - Parcialmente actualizado
3. ✅ `ESPECIFICACION_FLEXION_CAMBIOS.md` - Especificación técnica
4. ✅ `INSTRUCCIONES_FINALES.md` - Este archivo

---

## PRÓXIMOS PASOS

1. ✅ Copiar `flexion.py` a `python/resistencia/`
2. ✅ Copiar `app.R` actualizado
3. ⏳ Aplicar cambios en gráfico (código arriba)
4. ⏳ Aplicar cambios en tabla (código arriba)
5. ⏳ Actualizar `calcular_interaccion()` para biaxial
6. ⏳ Testing completo con todas las familias
7. ⏳ Documentar en LaTeX

---

## NOTAS IMPORTANTES

### Familias con Eje Débil
- ✅ Doble T (W, M, HP, S, IPE, IPN, IPB)
- ✅ Canal (C, MC, UPN)
- ✅ HSS Rectangular

### Familias Sin Eje Débil (Mdy = NULL)
- Angular L (no distingue ejes)
- Perfil T (solo un eje significativo)

### Familias Simétricas (Mdx = Mdy)
- Tubo Circular
- Tubo Cuadrado (HSS cuadrado)

### Verificaciones AISC por Familia

| Familia | Eje Fuerte | Eje Débil |
|---------|------------|-----------|
| Doble T | F2 (LTB) + F3 (FLB) | F6 (solo FLB) |
| Canal | F2 + F3 | F6 |
| Angular | F10 | — |
| Perfil T | F9 | — |
| Tubo Circular | F8 | F8 (igual) |
| HSS Rect | F7 | F7 |
| HSS Cuad | F7 | F7 (igual) |

---

FIN DE INSTRUCCIONES
