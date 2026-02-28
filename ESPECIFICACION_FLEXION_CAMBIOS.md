# ESPECIFICACIÓN DE CAMBIOS - flexion.py

## OBJETIVO

1. ✅ Agregar soporte para nuevas familias de perfiles
2. ✅ Implementar cálculo de flexión en eje débil (y-y)
3. ✅ Retornar resistencias Mdx (eje fuerte) y Mdy (eje débil)
4. ✅ Permitir selección de eje de flexión

---

## CAMBIOS IMPLEMENTADOS

### 1. Nuevas Familias Soportadas

#### Perfil T (WT, MT, ST, T)
**Verificación**: AISC F9 (stem en compresión - conservador)

```python
def _Mn_perfil_T(Fy, Sx, Zx, d_tw, E):
    """
    Límites:
    - λp = 0.84·√(E/Fy)
    - λr = 1.03·√(E/Fy)
    
    Casos:
    - d/tw ≤ λp: Mn = Mp (compacto)
    - λp < d/tw ≤ λr: Mn = Mp - (Mp-My)·(λ-λp)/(λr-λp)
    - d/tw > λr: Mn = min(Fcr·Sx, Mp) donde Fcr = 0.69E/λ²
    """
```

#### Tubo Circular (PIPE, TUBO CIRC.)
**Verificación**: AISC F8

```python
def _Mn_tubo_circular(Fy, Z, D_t, E):
    """
    Límite:
    - λp = 0.07·E/Fy
    
    Casos:
    - D/t ≤ λp: Mn = Mp (compacto)
    - D/t > λp: Mn reducido por factor (0.021E)/(D/t)
    """
```

#### Tubo Rectangular/Cuadrado (HSS, TUBO CUAD., TUBO RECT.)
**Verificación**: AISC F7

```python
def _Mn_HSS_rectangular(Fy, Sx, Zx, b_t, h_t, E):
    """
    Límites para flanges:
    - λpf = 1.12·√(E/Fy)
    - λrf = 1.40·√(E/Fy)
    
    Límites para webs:
    - λpw = 2.42·√(E/Fy)
    - λrw = 5.70·√(E/Fy)
    
    Verifica ambos elementos, gobierna el menor Mn
    """
```

---

### 2. Flexión en Eje Débil

#### Doble T y Canales (AISC F6)

```python
def _Mn_eje_debil(Fy, Sy, Zy, bf_2tf, E):
    """
    Solo FLB (no hay LTB para eje débil)
    
    Límites:
    - λp = 0.38·√(E/Fy)
    - λr = 1.0·√(E/Fy)
    
    Casos:
    - λ ≤ λp: Mn = Mp
    - λp < λ ≤ λr: Mn = Mp - (Mp-My)·(λ-λp)/(λr-λp)
    - λ > λr: Mn = min(Fcr·Sy, Mp) donde Fcr = 0.69E/λ²
    """
```

**Aplicable a**:
- Doble T: W, M, HP, S, IPE, IPN, IPB
- Canales: C, MC, UPN

**No aplicable a**:
- Angulares (no tiene sentido distinguir ejes)
- Perfiles T (solo un eje significativo)
- Tubos circulares (simétrico)
- Tubos rectangulares (calcular ambos ejes por separado)

---

### 3. Actualización de Firma de Función

**Antes**:
```python
def flexion(perfil_nombre, Fy, Lb, db_manager, 
            tipo_perfil=None, Cb=1.0, mostrar_calculo=True):
```

**Ahora**:
```python
def flexion(perfil_nombre, Fy, Lb, db_manager,
            tipo_perfil=None, 
            eje='fuerte',          # ← NUEVO
            Cb=1.0, 
            mostrar_calculo=True,
            calcular_ambos_ejes=False):  # ← NUEVO
```

**Nuevos Parámetros**:
- `eje`: 'fuerte' (x-x) o 'debil' (y-y)
- `calcular_ambos_ejes`: Si True, calcula y retorna ambos

---

### 4. Estructura de Retorno Actualizada

**Antes**:
```python
return {
    'Md': resistencia diseño eje fuerte [kN·m],
    'Mn': resistencia nominal [kN·m],
    'Mp': momento plástico [kN·m],
    'Lp', 'Lr': longitudes límite [mm],
    'modo': modo que gobierna
}
```

**Ahora**:
```python
return {
    # Eje fuerte (siempre presente)
    'Mdx': resistencia diseño eje fuerte [kN·m],
    'Mnx': resistencia nominal eje fuerte [kN·m],
    'Mpx': momento plástico eje fuerte [kN·m],
    'Lp', 'Lr': longitudes límite [mm],
    'modo_x': modo eje fuerte,
    
    # Eje débil (si aplicable y si calcular_ambos_ejes=True)
    'Mdy': resistencia diseño eje débil [kN·m] | None,
    'Mny': resistencia nominal eje débil [kN·m] | None,
    'Mpy': momento plástico eje débil [kN·m] | None,
    'modo_y': modo eje débil | None,
    
    # Compatibilidad hacia atrás
    'Md': Mdx (por defecto) o Mdy (si eje='debil'),
    'Mn': Mnx o Mny según eje
}
```

---

## LÓGICA DE CÁLCULO POR FAMILIA

### Doble T (W, M, HP, S, IPE, IPN, IPB)

**Eje Fuerte (x-x)**:
1. LTB: `_Mn_LTB()` con Lb, Lp, Lr
2. FLB: `_Mn_FLB()` con bf/2tf
3. Mn = min(Mn_LTB, Mn_FLB)

**Eje Débil (y-y)**:
1. Solo FLB: `_Mn_eje_debil()` con bf/2tf
2. No hay LTB (ala completa en compresión)

### Canal (C, MC, UPN)

**Eje Fuerte (x-x)**:
- Igual que Doble T (conservador)

**Eje Débil (y-y)**:
- Igual que Doble T

### Angular (L)

**Ambos ejes**:
- Mn = 1.5·My (F10 simplificado)
- No distingue ejes

### Perfil T (WT, MT, ST, T)

**Un solo eje significativo**:
- `_Mn_perfil_T()` con d/tw del stem
- Eje débil no relevante (simétrico respecto a stem)

### Tubo Circular (PIPE, TUBO CIRC.)

**Simétrico (un solo resultado)**:
- `_Mn_tubo_circular()` con D/t
- Mdx = Mdy

### Tubo Rectangular (HSS, TUBO CUAD., TUBO RECT.)

**Eje Fuerte (mayor dimensión)**:
- `_Mn_HSS_rectangular()` con b/t y h/t

**Eje Débil (menor dimensión)**:
- Intercambiar b y h, recalcular

---

## INTEGRACIÓN CON app.R

### Cambios en Llamadas

**Antes**:
```r
res <- flex_mod$flexion(
  perfil_nombre = nombre,
  tipo_perfil = tipo,
  Fy = Fy(),
  Lb = Lb_mm,
  db_manager = db_manager,
  mostrar_calculo = FALSE
)

Md <- res$Md  # Solo eje fuerte
```

**Ahora**:
```r
res <- flex_mod$flexion(
  perfil_nombre = nombre,
  tipo_perfil = tipo,
  Fy = Fy(),
  Lb = Lb_mm,
  db_manager = db_manager,
  calcular_ambos_ejes = TRUE,  # ← Calcular x e y
  mostrar_calculo = FALSE
)

Mdx <- res$Mdx  # Eje fuerte
Mdy <- res$Mdy  # Eje débil (puede ser NULL)
```

### Gráfico con Doble Eje

```r
# Plotly con eje secundario
p <- plot_ly()

# Eje fuerte (eje Y principal)
for (i in seq_along(curvas_Md)) {
  p <- p %>% add_trace(
    data = curvas_Md[[i]],
    x = ~Lb_m, y = ~Mdx,
    yaxis = "y",
    name = paste(nombre, "Mdx"),
    line = list(color = color, width = 2)
  )
  
  # Eje débil (eje Y secundario) - si existe
  if (!is.null(curvas_Md[[i]]$Mdy)) {
    p <- p %>% add_trace(
      data = curvas_Md[[i]],
      x = ~Lb_m, y = ~Mdy,
      yaxis = "y2",
      name = paste(nombre, "Mdy"),
      line = list(color = color, width = 2, dash = 'dash')
    )
  }
}

# Layout con doble eje
p <- p %>% layout(
  xaxis = list(title = "Lb [m]"),
  yaxis = list(title = "Mdx [kN·m]", side = "left"),
  yaxis2 = list(
    title = "Mdy [kN·m]",
    side = "right",
    overlaying = "y"
  )
)
```

---

## CAMBIOS EN app.R - INPUTS

### Eliminar Mu, Agregar Mux y Muy

**Antes** (línea ~780):
```r
numericInput("Nu", "Nu [kN]", value=0, min=0, max=10000),
numericInput("Mu", "Mu [kN·m]", value=0, min=0, max=5000),
```

**Ahora**:
```r
numericInput("Nu", "Nu [kN]", value=0, min=0, max=10000, width="100%"),
div(class="input-row-2",
  numericInput("Mux", "Mux [kN·m]", value=0, min=0, max=5000, width="48%"),
  numericInput("Muy", "Muy [kN·m]", value=0, min=0, max=5000, width="48%")
),
```

**CSS para Layout en 2 Columnas**:
```css
.input-row-2 {
  display: flex;
  gap: 4%;
  width: 100%;
}

.input-row-2 .shiny-input-container {
  flex: 1;
}
```

---

## MODIFICACIONES EN FUNCIONES R

### generar_curva_Md (actualizada)

```r
generar_curva_Md <- function(perfil_nombre, tipo_perfil, Fy) {
  Mdx_vec <- numeric(length(L_PUNTOS))
  Mdy_vec <- numeric(length(L_PUNTOS))
  
  for (i in seq_along(L_PUNTOS)) {
    tryCatch({
      res <- flex_mod$flexion(
        perfil_nombre = perfil_nombre,
        tipo_perfil = tipo_perfil,
        Fy = Fy,
        Lb = L_PUNTOS[i],
        db_manager = db_manager,
        calcular_ambos_ejes = TRUE,  # ← Nuevo
        Cb = 1.0,
        mostrar_calculo = FALSE
      )
      Mdx_vec[i] <- res$Mdx
      Mdy_vec[i] <- if (!is.null(res$Mdy)) res$Mdy else NA
    }, error = function(e) {
      Mdx_vec[i] <<- NA_real_
      Mdy_vec[i] <<- NA_real_
    })
  }
  
  data.frame(
    Lb_m = L_PUNTOS / 1000,
    Mdx = Mdx_vec,
    Mdy = Mdy_vec,
    perfil = perfil_nombre
  )
}
```

### calcular_Md_punto (actualizada)

```r
calcular_Md_punto <- function(perfil_nombre, tipo_perfil, Fy, Lb_mm) {
  tryCatch({
    res <- flex_mod$flexion(
      perfil_nombre = perfil_nombre,
      tipo_perfil = tipo_perfil,
      Fy = Fy,
      Lb = Lb_mm,
      db_manager = db_manager,
      calcular_ambos_ejes = TRUE,  # ← Nuevo
      Cb = 1.0,
      mostrar_calculo = FALSE
    )
    
    list(
      Mdx = res$Mdx,
      Mdy = if (!is.null(res$Mdy)) res$Mdy else NA,
      Mnx = res$Mnx,
      Mpx = res$Mpx,
      Lp = res$Lp,
      Lr = res$Lr,
      modo_x = res$modo_x,
      modo_y = if (!is.null(res$modo_y)) res$modo_y else NA,
      advertencias = res$advertencias
    )
  }, error = function(e) {
    list(Mdx = NA_real_, Mdy = NA_real_, error = conditionMessage(e))
  })
}
```

---

## TABLA DE RESULTADOS ACTUALIZADA

**Tab Flexión - Nueva Estructura**:

| Perfil | Mdx [kN·m] | Mdy [kN·m] | Lp [mm] | Lr [mm] | Modo |
|--------|------------|------------|---------|---------|------|
| IPE 100 | 18.5 | 3.2 | 1240 | 4580 | LTB inelástico |
| IPN 100 | 16.8 | 2.9 | 1180 | 4320 | LTB inelástico |

**Nota**: Mdy se muestra solo si está disponible (no para angulares, perfiles T)

---

## INTERACCIÓN (PRÓXIMA FASE)

Para interacción biaxial:

```python
def interaccion_biaxial(perfil, Fy, Lx, Ly, Lb, Nu, Mux, Muy, ...):
    """
    H1-1 con flexión biaxial:
    
    Si Nu/Pd ≥ 0.2:
        Nu/Pd + 8/9·(Mux/Mdx + Muy/Mdy) ≤ 1.0
    
    Si Nu/Pd < 0.2:
        Nu/(2·Pd) + (Mux/Mdx + Muy/Mdy) ≤ 1.0
    """
```

---

## RESUMEN DE ARCHIVOS A MODIFICAR

1. ✅ `flexion.py`:
   - Agregar funciones nuevas familias
   - Agregar función eje débil
   - Actualizar función principal
   - Actualizar retornos

2. ✅ `app.R`:
   - Cambiar Mu → Mux, Muy
   - Actualizar generar_curva_Md
   - Actualizar calcular_Md_punto
   - Actualizar gráfico con doble eje
   - Actualizar tabla resultados

3. ⏳ `interaccion.py` (próxima fase):
   - Actualizar para flexión biaxial

---

## TESTING SUGERIDO

```python
# Test 1: Doble T con ambos ejes
res = flexion('IPE 100', Fy=250, Lb=3000, 
              db_manager=db, calcular_ambos_ejes=True)
assert res['Mdx'] > res['Mdy']  # Fuerte > débil

# Test 2: Perfil T (solo un eje)
res = flexion('WT22X167.5', Fy=250, Lb=3000,
              db_manager=db, calcular_ambos_ejes=True)
assert res['Mdy'] is None  # No tiene eje débil

# Test 3: Tubo circular (simétrico)
res = flexion('PIPE 8 STD', Fy=250, Lb=3000,
              db_manager=db, calcular_ambos_ejes=True)
assert res['Mdx'] == res['Mdy']  # Simétrico

# Test 4: HSS rectangular
res = flexion('HSS10X6X1/4', Fy=250, Lb=3000,
              db_manager=db, calcular_ambos_ejes=True)
assert res['Mdx'] > res['Mdy']  # Mayor dimensión > menor
```

---

## PRÓXIMOS PASOS

1. ✅ Implementar cambios en `flexion.py`
2. ✅ Modificar `app.R` (inputs Mux/Muy, gráfico doble eje)
3. ⏳ Actualizar `interaccion.py` para flexión biaxial
4. ⏳ Testing completo con todas las familias
5. ⏳ Documentar ecuaciones en LaTeX
