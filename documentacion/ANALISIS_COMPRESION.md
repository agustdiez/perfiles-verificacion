# Análisis Técnico Completo: compresion.py

## Vista General

**Módulo**: `resistencia/compresion.py`  
**Propósito**: Calcular resistencia a compresión axial según CIRSOC 301 / AISC 360-10  
**Estado**: ✅ Implementación completa con soporte para 7 familias de perfiles

---

## Flujo Principal - 9 Pasos

### PASO 0: Inicialización LaTeX
```python
latex_doc = []
latex_doc.append(f"\\section{{Cálculo de Compresión: {perfil_nombre}}}")
```
- Prepara lista para documentación LaTeX del cálculo
- Cada paso agregará ecuaciones formateadas

### PASO 1: Obtener Datos del Perfil
```python
perfil = db_manager.obtener_datos_perfil(perfil_nombre)
bd_nombre = db_manager.nombre_base_activa()
tipo = str(perfil['Tipo']).strip()
```

**Acciones**:
- Consulta base de datos (CIRSOC o AISC)
- Obtiene fila completa del perfil
- Identifica tipo: W, C, L, T, TUBO CIRC., etc.

**Salida**: Serie de pandas con todas las columnas del perfil

---

### PASO 2: Extraer Propiedades Geométricas
```python
props = extraer_propiedades(perfil, base_datos=bd_nombre)
familia = props['familia']
verificacion = verificar_propiedades(props)
```

**Conversión de Unidades**:
- Input BD: cm², cm⁴, cm, kg/m (CIRSOC) o mm² (AISC)
- Output: **mm / mm² / mm⁴ / mm⁶** (todo en milímetros)

**Familias Detectadas**:
1. **DOBLE_T**: W, M, HP, S, IPE, IPN, IPB, IPBl, IPBv
2. **CANAL**: C, MC, UPN
3. **ANGULAR**: L
4. **PERFIL_T**: T, WT, MT, ST
5. **TUBO_CIRC**: TUBO CIRC., PIPE
6. **TUBO_CUAD**: TUBO CUAD., HSS (cuadrado)
7. **TUBO_RECT**: TUBO RECT., HSS (rectangular)

**Validación**:
```python
if not verificacion['completo']:
    raise ValueError("Propiedades faltantes: ...")
```

**Propiedades Extraídas**:
- `basicas`: d, bf, Ag, Peso
- `flexion`: Ix, Iy, Sx, Sy, Zx, Zy, rx, ry
- `torsion`: J, Cw
- `seccion`: tf, tw, hw, bf_2tf, hw_tw
- `centro_corte`: xo, yo, ro, H

---

### PASO 3: Ajustar Lz (Longitud Torsional)
```python
if Lz is None:
    Lz = max(Lx, Ly)
```

**Criterio**: Si no se especifica, usar la mayor longitud de pandeo flexional

---

### PASO 4: Inicializar Resultados
```python
resultados = {
    'Q': 1.0, 'Qs': 1.0, 'Qa': 1.0,  # Factor reducción secciones esbeltas
    'iter_Q': 0,
    'advertencias': [],
    # ... parámetros de entrada
}
```

**Valores Iniciales**:
- Q = 1.0 (sin reducción, se ajusta si es esbelta)
- Advertencias = lista vacía
- Copia de todos los parámetros de entrada

---

### PASO 5: Variables de Trabajo
```python
A = props['basicas']['Ag']
rx = props['flexion']['rx']
ry = props['flexion']['ry']
J = props['torsion']['J']
Cw = props['torsion']['Cw']
xo, yo, ro, H = props['centro_corte'][...]
```

**Propósito**: 
- Extraer propiedades clave a variables locales
- Todas garantizadas en mm / mm² / mm⁴
- Agregar al dict `resultados` para trazabilidad

---

### PASO 6: Clasificación de Sección
```python
clasificacion = clasificar_seccion(props, Fy, E=E_ACERO, mostrar=mostrar_calculo)
clase_seccion = clasificacion['clase_seccion']
es_esbelta = clasificacion['es_esbelta']
```

**Llamada al Módulo**: `clasificacion/clasificacion_seccion.py`

**Criterios AISC 360-10 Table B4.1**:

| Elemento | λ | λp | λr | Clasificación |
|----------|---|----|----|---------------|
| Ala | bf/2tf | Variable según Fy | Variable | Si λ ≤ λp → COMPACTA |
| Alma | hw/tw | Variable según Fy | Variable | Si λp < λ ≤ λr → NO_COMPACTA |
| | | | | Si λ > λr → ESBELTA |

**Clases**:
- **COMPACTA**: Puede alcanzar Mp sin pandeo local
- **NO_COMPACTA**: Pandeo local antes de Mp, después de My
- **ESBELTA**: Pandeo local antes de My → requiere Q < 1.0

**Salida**:
```python
{
    'clase_seccion': 'COMPACTA' | 'NO_COMPACTA' | 'ESBELTA',
    'es_esbelta': bool,
    'elementos': {
        'ala': {'lambda': ..., 'lambda_p': ..., 'lambda_r': ...},
        'alma': {...}
    },
    'advertencias': [...]
}
```

---

### PASO 6.5: Cálculo Iterativo de Q (Solo si ESBELTA)

**Condición**: `if clasificacion['es_esbelta']:`

**Proceso Iterativo**:

```python
# 1. Calcular Fe temporal (preliminar)
if familia == 'DOBLE_T':
    Fe_x_temp, _ = _fe_flexional(KxLx, rx)
    Fe_y_temp, _ = _fe_flexional(KyLy, ry)
    Fe_z_temp = _fe_torsional(J, Cw, Kz, Lz, A, ro)
    Fe_temp = min(Fe_x_temp, Fe_y_temp, Fe_z_temp)

# 2. Iteración
Q_actual = 1.0
for iter_Q in range(1, max_iter_Q + 1):
    # a) Fcr temporal con Q actual
    Fcr_temporal = _calcular_Fcr(Fe_temp, Fy, Q=Q_actual)
    
    # b) Calcular nuevo Q con Fcr temporal
    Q_info = calcular_Q(props, Fy, E_ACERO, Fcr=Fcr_temporal)
    Q_nuevo = Q_info['Q']
    Qs = Q_info['Qs']  # Factor elementos no rigidizados (alas)
    Qa = Q_info['Qa']  # Factor elementos rigidizados (almas)
    
    # c) Verificar convergencia
    error_relativo = abs(Q_nuevo - Q_actual) / Q_actual
    if error_relativo < tol_Q:  # default: 0.01 = 1%
        break
    
    Q_actual = Q_nuevo

# 3. Actualizar resultados
resultados['Q'] = Q_nuevo
resultados['Qs'] = Qs
resultados['Qa'] = Qa
resultados['iter_Q'] = iter_Q
```

**Fórmula Q**:
```
Q = Qs × Qa

Qs = factor de reducción por elementos no rigidizados (alas)
Qa = factor de reducción por elementos rigidizados (almas)
```

**Criterio de Convergencia**:
- Error relativo < 1% (configurable)
- Máximo 5 iteraciones (configurable)
- Si no converge → advertencia

**Por qué es Iterativo**:
- Fcr depende de Q: `Fcr = f(Fe, Fy, Q)`
- Q depende de Fcr: `Q = f(Fcr)`
- Solución: iteración hasta convergencia

---

### PASO 7: Pandeo Global - Cálculo de Fe

**Objetivo**: Determinar tensión crítica elástica Fe según modo de pandeo

#### 7.1 DOBLE_T (y familias nuevas similares)

**Aplica a**: W, M, HP, IPE, IPN, IPB, PERFIL_T, TUBO_CIRC, TUBO_CUAD, TUBO_RECT

**Modos de Pandeo**:

1. **Flexional eje X**:
```python
Fe_x = π² × E / (KxLx/rx)²
esbeltez_x = KxLx / rx
```

2. **Flexional eje Y**:
```python
Fe_y = π² × E / (KyLy/ry)²
esbeltez_y = KyLy / ry
```

3. **Torsional puro**:
```python
Fe_z = (π² × E × Cw / (KzLz)² + G × J) / (Ag × ro²)
```
Ref: AISC 360-10 ecuación E4-4

**Resultado**:
```python
Fe = min(Fe_x, Fe_y, Fe_z)
modo_governa = 'Flexional_X' | 'Flexional_Y' | 'Torsional_Z'
esbeltez_max = max(esbeltez_x, esbeltez_y)
```

**Verificación**:
```python
if esbeltez_max > 200:
    advertencias.append("KL/r > 200 (límite CIRSOC 301)")
```

---

#### 7.2 CANAL

**Aplica a**: C, MC, UPN

**Modos de Pandeo**:

1. **Flexional eje X**: Igual que DOBLE_T

2. **Flexo-torsional Y-Z** (combinado):
```python
Fe_y = π² × E / (KyLy/ry)²
Fe_z = (π² × E × Cw / (KzLz)² + G × J) / (Ag × ro²)

# Si H > 0 y xo > 0:
Fe_yzt = (Fe_y + Fe_z)/(2H) × [1 - √(1 - 4·Fe_y·Fe_z·H/(Fe_y+Fe_z)²)]

# Si no hay H o xo:
Fe_yzt = Fe_y  (conservador)
```
Ref: AISC 360-10 ecuación E4-2

**Parámetro H**:
```
H = 1 - (xo²/ro²)

xo = distancia del centroide al centro de corte
ro = radio polar de giro respecto al centro de corte
```

**Resultado**:
```python
Fe = min(Fe_x, Fe_yzt)
modo_governa = 'Flexional_X' | 'Flexo_torsional_YZ'
```

---

#### 7.3 ANGULAR

**Aplica a**: L

**Modo de Pandeo**: Flexional respecto al eje principal menor

```python
iv = radio de giro del eje principal menor
KL_angular = max(KxLx, KyLy, KzLz)

Fe_iv = π² × E / (KL_angular/iv)²

Fe = Fe_iv
modo_governa = 'Flexional_iv'
esbeltez_max = KL_angular / iv
```

**Nota**: Para angulares, no hay distinción entre ejes x-y; se usa el radio iv directamente.

---

### PASO 8: Resistencia Final (Fcr, Pn, Pd)

#### 8.1 Cálculo de Fcr (Tensión Crítica)

**Fórmula AISC 360-10 E3/E7**:

```python
ratio = Q × Fy / Fe

if ratio ≤ 2.25:
    # Pandeo inelástico
    Fcr = 0.658^ratio × Q × Fy
else:
    # Pandeo elástico
    Fcr = 0.877 × Fe
```

**Interpretación**:
- `ratio ≤ 2.25`: Columna corta/intermedia (pandeo inelástico)
- `ratio > 2.25`: Columna esbelta (pandeo elástico)

**Efecto de Q**:
- Q = 1.0: sección compacta/no compacta, sin reducción
- Q < 1.0: sección esbelta, reducción por pandeo local

---

#### 8.2 Resistencia Nominal y de Diseño

```python
Pn = Fcr × A     # Resistencia nominal [N]
Pd = φc × Pn     # Resistencia de diseño [N]

φc = 0.90        # Factor de reducción LRFD para compresión
```

**Conversión a kN**:
```python
resultados['Pn'] = round(Pn / 1000, 2)  # kN
resultados['Pd'] = round(Pd / 1000, 2)  # kN
```

---

### PASO 9: Salida (Return)

**Diccionario Completo**:
```python
{
    # Identificación
    'perfil': str,
    'tipo': str,
    'familia': str,
    'base_datos': 'CIRSOC' | 'AISC',
    
    # Parámetros entrada
    'Fy': float,
    'Lx': float, 'Ly': float, 'Lz': float,
    'Kx': float, 'Ky': float, 'Kz': float,
    
    # Propiedades
    'A': float, 'rx': float, 'ry': float,
    'J': float, 'Cw': float,
    'ro': float, 'H': float,
    
    # Clasificación
    'clase_seccion': str,
    'clasificacion': dict,
    
    # Factor Q (secciones esbeltas)
    'Q': float,
    'Qs': float,
    'Qa': float,
    'iter_Q': int,
    'Q_notas': list,
    
    # Pandeo global
    'modos_Fe': dict,
    'Fe': float,
    'modo_pandeo': str,
    'esbeltez_x': float,
    'esbeltez_y': float,
    'esbeltez_max': float,
    
    # Resistencias
    'Fcr': float,  # [MPa]
    'Pn': float,   # [kN]
    'Pd': float,   # [kN]
    
    # Documentación
    'latex': str,
    'advertencias': list,
    
    # Constantes
    'E': 200_000,   # [MPa]
    'G': 77_200,    # [MPa]
    'phi_c': 0.90,
}
```

---

## Funciones Auxiliares

### _fe_flexional(KL, r)
```python
esbeltez = KL / r
Fe = π² × E / esbeltez²
return Fe, esbeltez
```
**Ecuación de Euler** para pandeo flexional

---

### _fe_torsional(J, Cw, Kz, Lz, Ag, ro)
```python
Fe_z = (π² × E × Cw / (Kz×Lz)² + G × J) / (Ag × ro²)
return Fe_z
```
**AISC 360-10 E4-4** - Pandeo torsional puro (doble simetría)

---

### _fe_flexotorsional_canal(Fe_y, Fe_z, H)
```python
suma = Fe_y + Fe_z
Fe = suma/(2H) × [1 - √(1 - 4×Fe_y×Fe_z×H/suma²)]
return Fe
```
**AISC 360-10 E4-2** - Pandeo flexo-torsional (simetría simple)

---

### _calcular_Fcr(Fe, Fy, Q=1.0)
```python
QFy = Q × Fy
ratio = QFy / Fe

if ratio ≤ 2.25:
    Fcr = (0.658 ** ratio) × QFy
else:
    Fcr = 0.877 × Fe

return Fcr
```
**AISC 360-10 E3-2, E3-3, E7-2, E7-3** - Tensión crítica

---

## Constantes del Módulo

```python
E_ACERO = 200_000  # [MPa] - Módulo de elasticidad
G_ACERO =  77_200  # [MPa] - Módulo de corte
PHI_C   =    0.90  # [-]   - Factor reducción LRFD compresión
```

---

## Gestión de Advertencias

**Tipos de Advertencias**:

1. **Propiedades opcionales faltantes**:
   - "J no disponible — cálculo de pandeo torsional puede ser impreciso"

2. **Esbeltez excesiva**:
   - "KL/r = 250 supera el límite de 200 (CIRSOC 301)"

3. **H o xo no disponibles (canales)**:
   - "xo/H no disponibles — pandeo flexo-torsional calculado con Fe_y (conservador)"

4. **Convergencia de Q**:
   - ✓ "Factor Q convergió en 3 iteraciones: Q = 0.8456"
   - ⚠️ "ADVERTENCIA: Factor Q no convergió en 5 iteraciones"

5. **Clasificación de sección**:
   - "Sección COMPACTA: Q = 1.0 (sin reducción)"
   - "Ala ESBELTA: bf/2tf = 12.5 > λr = 10.8"

---

## Generación de LaTeX

**Documentación Matemática Automática**:

```latex
\section{Cálculo de Compresión: W18X97}
\text{Base de datos: CIRSOC}

A = 123.87 \, \text{cm}^2
r_x = 18.67 \, \text{cm}, \quad r_y = 4.83 \, \text{cm}
r_o = 19.15 \, \text{cm}

\subsection{Cálculo de Factor Q (Sección Esbelta)}
\text{Iter. 1: } Q = 0.8500 (Q_s = 0.9200, Q_a = 0.9239), ...

\lambda_x = \frac{K_x L_x}{r_x} = \frac{1.0 \times 5000}{186.7} = 26.79
F_{e,x} = \frac{\pi^2 E}{\lambda_x^2} = ... = 2753.21 \, \text{MPa}

F_e = \min(F_{e,x}, F_{e,y}, F_{e,z}) = 1234.56 \, \text{MPa} \quad (\text{Flexional_Y})

\frac{Q F_y}{F_e} = 0.172 \leq 2.25 \rightarrow F_{cr} = 0.658^{0.172} \times 250 = 238.45 \, \text{MPa}

P_n = F_{cr} \times A_g = 238.45 \times 123.87 = 2953.21 \, \text{kN}
P_d = \phi_c P_n = 0.9 \times 2953.21 = 2657.89 \, \text{kN}
```

**Uso**: Puede copiarse directamente a documentos técnicos

---

## Flujo de Ejecución Completo

```
INICIO
  ↓
[1] Obtener datos BD → perfil (Serie pandas)
  ↓
[2] Extraer props → mm/mm²/mm⁴ + familia
  ↓
[3] Ajustar Lz
  ↓
[4] Inicializar resultados (Q=1.0)
  ↓
[5] Asignar variables (A, rx, ry, J, Cw, ro, H)
  ↓
[6] Clasificar sección → COMPACTA | NO_COMPACTA | ESBELTA
  ↓
  ┌─── ¿Es ESBELTA? ───┐
  │                     │
 NO                    SÍ
  │                     ↓
  │           [6.5] Calcular Q iterativo
  │                 ↓
  │           FOR iter = 1 to 5:
  │                 ↓
  │           Fcr_temp = f(Fe_temp, Fy, Q)
  │                 ↓
  │           Q_nuevo = calcular_Q(Fcr_temp)
  │                 ↓
  │           error < 1%? → BREAK
  │                 ↓
  └─────────────────┘
  ↓
[7] Calcular Fe según familia
  ↓
  ┌─── ¿Familia? ────┐
  │                  │
DOBLE_T          CANAL          ANGULAR
  │                  │              │
  ↓                  ↓              ↓
Fe_x, Fe_y,      Fe_x,          KL/iv
Fe_z             Fe_yzt           ↓
  ↓                  ↓            Fe_iv
Fe = min(...)    Fe = min(...)    │
  │                  │              │
  └──────────────────┴──────────────┘
  ↓
esbeltez_max, modo_pandeo
  ↓
[8] Calcular Fcr, Pn, Pd
  ↓
ratio = Q·Fy/Fe
  ↓
  ┌─── ratio ≤ 2.25? ───┐
  │                      │
 SÍ                     NO
  ↓                      ↓
Fcr = 0.658^ratio    Fcr = 0.877·Fe
    × Q·Fy
  │                      │
  └──────────────────────┘
  ↓
Pn = Fcr × A
Pd = 0.90 × Pn
  ↓
[9] Generar LaTeX, reportar
  ↓
RETURN dict
  ↓
FIN
```

---

## Nuevas Funcionalidades Comentadas

### 1. Soporte de Tubos y Perfiles T
**Implementado**: ✅  
Los perfiles T y tubos usan el mismo flujo que DOBLE_T:
- Fe_x, Fe_y, Fe_z calculados igual
- Propiedades extraídas por `utilidades_perfil.py`

### 2. Pandeo Local en Tubos
**Pendiente**: ⚠️  
Tubos necesitan verificación D/t para pandeo local según AISC E7:
```python
# Para tubos circulares
D_t = D / t
lambda_r = 0.11 × E / Fy

if D_t > lambda_r:
    # Calcular Fcr reducido por pandeo local
```

### 3. Perfiles con Arriostramiento Parcial
**Pendiente**: 💡  
Considerar casos donde Lz ≠ max(Lx, Ly):
- Arriostramiento torsional independiente
- Casos con K diferentes en cada dirección

### 4. Pandeo Flexo-Torsional en Tubos Rectangulares
**Pendiente**: 💡  
Tubos rectangulares pueden tener pandeo flexo-torsional:
```python
# Similar a canales, pero con H calculado diferente
if familia == 'TUBO_RECT':
    # Implementar ecuaciones E4-5, E4-6 de AISC
```

### 5. Efectos de Temperatura
**Pendiente**: 💡  
Reducción de E y Fy con temperatura:
```python
def ajustar_por_temperatura(E, Fy, T_celsius):
    # AISC Appendix 4
    if T > 100:
        E_T = E × factor_E(T)
        Fy_T = Fy × factor_Fy(T)
    return E_T, Fy_T
```

### 6. Perfiles Compuestos
**No soportado**: ❌  
Actualmente solo perfiles simples. Para perfiles compuestos:
- Calcular propiedades transformadas
- Considerar acción compuesta
- Pandeo individual de componentes

### 7. Optimización de Convergencia Q
**Mejorable**: 🔧  
Método actual: iteración simple  
Propuesta: Newton-Raphson para convergencia más rápida
```python
def calcular_Q_newton(props, Fy, E, Fe):
    # Usar derivada analítica de Q respecto a Fcr
    # Convergencia en ~2 iteraciones vs 5
```

---

## Recomendaciones de Debugging

### Puntos Críticos de Falla

1. **Propiedades faltantes**:
   - Verificar que `verificar_propiedades()` no falle
   - Agregar debug prints en extracción

2. **División por cero**:
   - `ro = 0` en pandeo torsional
   - `r = 0` en cálculo de esbeltez
   - Validar antes de calcular Fe

3. **Valores negativos en raíz cuadrada**:
   - En `_fe_flexotorsional_canal()`
   - Validar discriminante ≥ 0

4. **Convergencia infinita de Q**:
   - Verificar max_iter_Q
   - Agregar logging de cada iteración

5. **Familia no reconocida**:
   - Agregar nuevas familias en if/elif
   - ValueError debe ser descriptivo

### Testing Sugerido

```python
# Test suite
def test_doble_t_compacta():
    """W18X97 compacta → Q = 1.0"""
    
def test_canal_esbelta():
    """C15x50 esbelta → Q < 1.0, convergencia"""
    
def test_angular():
    """L 4x4x1/2 → modo iv"""
    
def test_tubo_circular():
    """PIPE 26STD → pandeo torsional"""
    
def test_perfil_t():
    """WT22X167.5 → igual que doble T"""

def test_esbeltez_limite():
    """KL/r > 200 → advertencia"""
    
def test_convergencia_Q():
    """Q debe converger en < 5 iter"""
```

---

## Trazabilidad Completa

Cada valor calculado tiene origen rastreable:
1. Props → `extraer_propiedades()` → conversión unidades documentada
2. Q → `calcular_Q()` → fórmulas AISC E7
3. Fe → ecuaciones Euler/torsión → AISC E4
4. Fcr → `_calcular_Fcr()` → AISC E3/E7
5. LaTeX → ecuaciones paso a paso

**Auditoría**: Seguir cualquier número desde input → output
