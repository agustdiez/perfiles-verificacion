# SteelCheck v0.5 — Rediseño Completo

## Cambios Principales

### 🎨 Diseño Visual Renovado

**De Modo Oscuro → Modo Claro Profesional**

- **Fondo**: Gradiente suave gris claro (`#f8fafc` → `#e2e8f0`)
- **Cards**: Blancas con sombras sutiles y bordes redondeados (12px)
- **Tipografía moderna**:
  - `Inter`: Texto general (clean, legible)
  - `Outfit`: Títulos y números (bold, distintivo)
  - `JetBrains Mono`: Código y datos técnicos

### 🎯 Paleta de Colores

| Elemento | Color | Uso |
|----------|-------|-----|
| **Primario** | `#ef4444` (Rojo) | CTA principal, compresión |
| **Secundario** | `#3b82f6` (Azul) | Flexión, botones secundarios |
| **Success** | `#10b981` (Verde) | Serviciabilidad, estado OK |
| **Purple** | `#8b5cf6` | Interacción |
| **Orange** | `#f59e0b` | Alertas, info |
| **Cyan** | `#06b6d4` | Tubos cuadrados |
| **Pink** | `#ec4899` | Tubos rectangulares |

### 📊 Componentes Rediseñados

#### Cards Modernas
```css
.card-modern {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05), 
              0 4px 12px rgba(0,0,0,0.04);
  padding: 24px;
  transition: transform 0.2s;
}

.card-modern:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 6px rgba(0,0,0,0.07), 
              0 12px 24px rgba(0,0,0,0.08);
}
```

#### Profile Cards
- Fondo gris claro (`#f8fafc`)
- Bordes suaves con transiciones
- Indicadores de color circulares con sombra
- Layout flexible para familia + perfil + botón

#### Botones
**Calcular (CTA Principal)**:
- Gradiente rojo (#ef4444 → #dc2626)
- Sombra pronunciada con color primario
- Hover: lift effect + sombra más intensa

**Ver Propiedades**:
- Gradiente azul (#3b82f6 → #2563eb)
- Tamaño compacto (42x42px)
- Icono "=" centrado

**Acciones Secundarias**:
- Fondo blanco con borde
- Hover: cambio sutil de fondo

### 🆕 Soporte de Perfiles Actualizado

#### Familias Nuevas Soportadas

El selector de familias ahora incluye automáticamente:

**CIRSOC (16 familias)**:
- W, M, HP (Doble T americanos)
- IPN, IPE, IPB, IPBl, IPBv (Doble T europeos)
- C, MC, UPN (Canales)
- L (Angulares)
- **T** ← NUEVO (Perfiles T)
- **TUBO CIRC.** ← NUEVO (Tubos circulares)
- **TUBO CUAD.** ← NUEVO (Tubos cuadrados)
- **TUBO RECT.** ← NUEVO (Tubos rectangulares)

**AISC (13 familias)**:
- W, M, HP, S (Doble T)
- C, MC (Canales)
- L, 2L (Angulares)
- **WT, MT, ST** ← NUEVO (Perfiles T)
- **PIPE** ← NUEVO (Tubos circulares)
- **HSS** ← NUEVO (Tubos cuadrados/rectangulares)

#### Sistema de Colores por Familia

Modal de propiedades con badge de familia:

```r
badge_color <- switch(familia,
  DOBLE_T = "#3b82f6",     # Azul
  CANAL = "#10b981",       # Verde
  ANGULAR = "#ef4444",     # Rojo
  PERFIL_T = "#8b5cf6",    # Púrpura
  TUBO_CIRC = "#f59e0b",   # Naranja
  TUBO_CUAD = "#06b6d4",   # Cyan
  TUBO_RECT = "#ec4899",   # Rosa
  "#64748b"                # Gris (default)
)
```

### 📱 Resultados Mejorados

#### Cajas de Resultado
- Borde izquierdo de 4px con color del perfil
- Fondo blanco con bordes redondeados
- Hover: sombra sutil
- Layout de 2 columnas: info + valores

#### Estado de Interacción
**Cumple**:
```html
<div class="status-badge status-ok">
  ✓ CUMPLE
</div>
```
- Fondo: gradiente verde (#d1fae5 → #a7f3d0)
- Texto: verde oscuro (#065f46)

**No Cumple**:
```html
<div class="status-badge status-fail">
  ✗ NO CUMPLE
</div>
```
- Fondo: gradiente rojo (#fee2e2 → #fecaca)
- Texto: rojo oscuro (#991b1b)

#### Tablas de Serviciabilidad
- Headers con colores diferenciados (azul/verde)
- Bordes inferiores de 2px para separar ejes
- Hover: fondo gris muy claro
- Valores en negrita para mejor legibilidad

### 🎯 Header Renovado

```css
.app-header {
  background: white;
  border-radius: 16px;
  padding: 28px 32px;
  box-shadow: [doble sombra suave];
  border-bottom: 4px solid #ef4444;
}

.app-title {
  font-family: 'Outfit';
  font-size: 36px;
  font-weight: 800;
  background: linear-gradient(135deg, #ef4444, #dc2626);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

Resultado: título con gradiente rojo, subtítulo en monospace, version tag con gradiente azul.

### 📊 Gráficos

**Mejoras visuales**:
- Fondo blanco puro
- Grid gris muy claro (#f1f5f9)
- Leyenda con fondo blanco semi-transparente
- Marcadores circulares con borde blanco
- Líneas de 3px de grosor

### 📋 Info Chips

Chips informativos para mostrar estadísticas:

```html
<span class="info-chip">📊 879 perfiles</span>
<span class="info-chip">📁 16 familias</span>
<span class="info-chip">⚖️ 0.2-498.5 kg/m</span>
```

Estilo: fondo gris claro, bordes redondeados, emoji + texto en monospace.

### 🎨 Detalles de Diseño

#### Sombras Estratificadas
- **Nivel 1** (cards): sombra sutil doble
- **Nivel 2** (hover): sombra más pronunciada
- **Nivel 3** (botones): sombra con tinte del color

#### Transiciones Suaves
- Todas las interacciones con `transition: 0.2s`
- Transform en hover para efecto de "levitación"
- Cambios de color suaves

#### Scrollbars Personalizadas
```css
::-webkit-scrollbar {
  width: 8px;
}
::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}
```

### 🔧 Funcionalidad Preservada

**Todo el código de cálculo original se mantiene**:
- ✓ Curvas de compresión (Pd vs L)
- ✓ Curvas de flexión (Md vs Lb)
- ✓ Ecuaciones de interacción H1-1
- ✓ Análisis de serviciabilidad
- ✓ Exportación a TXT
- ✓ Generación de LaTeX
- ✓ Modal de propiedades completas

**Mejoras en funcionalidad**:
- Actualización automática de familias según base de datos
- Soporte dinámico para todos los tipos de perfiles
- Colores de familia en modales de propiedades
- Info chips con estadísticas actualizadas

### 📦 Dependencias

Fuentes de Google Fonts importadas:
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
```

Librerías R:
- `shiny`
- `bslib` (con tema personalizado)
- `plotly` (gráficos interactivos)
- `reticulate` (integración Python)
- `shinycssloaders` (spinners de carga)

### 🎯 Principios de Diseño Aplicados

1. **Jerarquía Visual Clara**
   - Títulos grandes en Outfit
   - Contenido en Inter
   - Datos técnicos en JetBrains Mono

2. **Consistencia de Color**
   - Cada perfil tiene su color
   - Cada tipo de análisis tiene su color
   - Estados (OK/Fail) con colores universales

3. **Espaciado Generoso**
   - Padding: 24px en cards
   - Gap: 8-12px en elementos relacionados
   - Margin: 12-20px entre secciones

4. **Feedback Visual**
   - Hover effects en todos los elementos interactivos
   - Sombras que cambian con interacción
   - Transiciones suaves (0.2s)

5. **Accesibilidad**
   - Contraste alto (texto oscuro sobre fondo claro)
   - Tamaños de fuente legibles (11-36px)
   - Estados claramente diferenciados

### 🚀 Cómo Usar

```r
# En el directorio del proyecto
Sys.setenv(STEELCHECK_ROOT = getwd())
shiny::runApp("app.R")
```

La aplicación:
1. Carga las bases de datos CIRSOC y AISC
2. Permite seleccionar hasta 3 perfiles para comparar
3. Calcula automáticamente curvas de compresión y flexión
4. Verifica interacción N-M
5. Analiza serviciabilidad
6. Exporta resultados detallados

### 📸 Resumen Visual

**Antes (v0.4)**:
- Fondo oscuro (#0f1117)
- Estética minimalista/terminal
- Colores apagados

**Ahora (v0.5)**:
- Fondo claro con gradiente
- Estética moderna/profesional
- Colores vibrantes y gradientes
- Cards flotantes con sombras
- Tipografía de alta calidad
- Efectos hover sofisticados

---

## Compatibilidad

✓ **Código Python**: Sin cambios necesarios
✓ **Bases de datos**: Funciona con ambas actualizadas
✓ **Cálculos**: Toda la lógica original preservada
✓ **Familias**: Detecta automáticamente tipos disponibles

**Resultado**: Interfaz moderna y profesional manteniendo 100% de funcionalidad.
