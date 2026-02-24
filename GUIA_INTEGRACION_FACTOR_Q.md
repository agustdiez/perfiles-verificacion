# GUÍA DE INTEGRACIÓN - Factor Q en Verificaciones
# ==================================================

## 1. CONCEPTOS CLAVE

### Factor Q (AISC E7)
- **Q = Qs × Qa**
- **Qs**: elementos no rigidizados (unstiffened) → alas de doble T, canal, ángulos
- **Qa**: elementos rigidizados (stiffened) → almas de doble T, canal
- **0.35 ≤ Qs ≤ 0.76** (límites AISC)
- **Q = 1.0** si sección NO es esbelta

### Cuándo usar Q
- **COMPACTA**: Q = 1.0 (no aplicar reducción)
- **NO_COMPACTA**: Q = 1.0 (no aplicar reducción)
- **ESBELTA**: Q < 1.0 (aplicar reducción según AISC E7)

---

## 2. INTEGRACIÓN EN compresion.py

### Modificaciones necesarias:

```python
from clasificacion_seccion import clasificar_seccion, calcular_Q

def verificar_compresion(props, Fy, L, K, E=200_000):
    """
    Verificación a compresión con factor Q para elementos esbeltos
    """
    
    # 1. Clasificar sección
    resultado = clasificar_seccion(props, Fy, E, mostrar=False)
    
    # 2. Determinar Q
    if resultado['es_esbelta']:
        # Iteración para calcular Q y Fcr consistentemente
        Q = 1.0  # Primera iteración
        
        for i in range(3):  # Máximo 3 iteraciones
            # Calcular Fe (tensión elástica de pandeo)
            Fe = calcular_Fe(props, L, K, E)
            
            # Calcular Fcr según AISC E7-2 o E7-3
            if (K*L/r) <= 4.71 * np.sqrt(E / (Q*Fy)):
                Fcr = Q * Fy * (0.658 ** (Q*Fy/Fe))
            else:
                Fcr = 0.877 * Fe
            
            # Recalcular Q con Fcr obtenido
            Q_info = calcular_Q(props, Fy, E, Fcr=Fcr)
            Q_nuevo = Q_info['Q']
            
            # Verificar convergencia
            if abs(Q_nuevo - Q) / Q < 0.01:  # 1% tolerancia
                break
            Q = Q_nuevo
    else:
        Q = 1.0
    
    # 3. Calcular capacidad nominal
    Pn = Fcr * props['seccion']['A']  # [N]
    
    # 4. Capacidad de diseño
    Phi = 0.90  # LRFD
    Omega = 1.67  # ASD
    
    Pn_LRFD = Phi * Pn / 1000  # [kN]
    Pn_ASD = Pn / Omega / 1000  # [kN]
    
    return {
        'Pn_LRFD': Pn_LRFD,
        'Pn_ASD': Pn_ASD,
        'Fcr': Fcr,
        'Q': Q,
        'es_esbelta': resultado['es_esbelta']
    }
```

### Fórmulas AISC E7 para Fcr:

**Caso (a): KL/r ≤ 4.71√(E/QFy)**
```
Fcr = Q·Fy·[0.658^(QFy/Fe)]
```

**Caso (b): KL/r > 4.71√(E/QFy)**
```
Fcr = 0.877·Fe
```

Donde:
- Fe = π²E / (KL/r)²  para secciones doblemente simétricas
- Fe debe calcularse con las ecuaciones apropiadas para cada tipo de pandeo

---

## 3. INTEGRACIÓN EN flexion.py

### Para flexión pura (sin compresión):

El factor Q **NO se aplica directamente** en flexión pura según AISC. 
Las secciones esbeltas en flexión usan:
- **Tabla F5** para elementos con rigidizadores longitudinales
- **Método del ancho efectivo** para almas esbeltas
- **Reducción de Mn** por pandeo local del ala comprimida

Sin embargo, si tienes **flexocompresión** (H1):
```python
# Verificación de interacción flexocompresión
if Pr/Pc >= 0.2:
    # Ecuación H1-1a
    ratio = Pr/Pc + (8/9)*(Mrx/Mcx + Mry/Mcy)
else:
    # Ecuación H1-1b  
    ratio = Pr/(2*Pc) + (Mrx/Mcx + Mry/Mcy)

# Donde Pc se calcula con Q si es esbelta en compresión
```

### Para lateral-torsional buckling:

El cálculo de Mn para LTB (AISC F2) **no usa Q directamente**, pero:
- Si el ala comprimida es esbelta → usar F3 (no compactas/esbeltas)
- Q afecta indirectamente si hay compresión axial simultánea

---

## 4. EJEMPLO COMPLETO DE FLUJO

```python
# ============================================
# EJEMPLO: Perfil W con elementos esbeltos
# ============================================

from clasificacion_seccion import clasificar_seccion, calcular_Q
import numpy as np

# Propiedades del perfil (extraídas previamente)
props = {
    'tipo': 'W',
    'geometria': {'h': 400, 'tf': 6, 'bf': 200},
    'seccion': {
        'A': 8000,      # mm²
        'Ix': 50e6,     # mm⁴
        'rx': 79,       # mm
        'bf_2tf': 16.7, # ESBELTA
        'hw_tw': 65     # ESBELTA
    }
}

# Parámetros
Fy = 250  # MPa
E = 200_000  # MPa
L = 6000  # mm
K = 1.0

# ------------------------------------------------
# PASO 1: Clasificación
# ------------------------------------------------
resultado = clasificar_seccion(props, Fy, E, mostrar=True)

if resultado['es_esbelta']:
    print("\n⚠️  SECCIÓN ESBELTA → Aplicar Q")
    
    # ------------------------------------------------
    # PASO 2: Iteración Q - Fcr
    # ------------------------------------------------
    Q = 1.0
    r = props['seccion']['rx']
    
    for iteracion in range(5):
        # Esbeltez
        KLr = K * L / r
        
        # Tensión elástica de pandeo
        Fe = np.pi**2 * E / KLr**2
        
        # Límite para determinar ecuación
        limite = 4.71 * np.sqrt(E / (Q * Fy))
        
        # Calcular Fcr
        if KLr <= limite:
            Fcr = Q * Fy * (0.658 ** (Q * Fy / Fe))
        else:
            Fcr = 0.877 * Fe
        
        # Calcular Q con Fcr actual
        Q_info = calcular_Q(props, Fy, E, Fcr=Fcr)
        Q_nuevo = Q_info['Q']
        
        # Convergencia
        error = abs(Q_nuevo - Q) / Q * 100
        print(f"  Iter {iteracion+1}: Q={Q_nuevo:.4f}, Fcr={Fcr:.2f} MPa, error={error:.2f}%")
        
        if error < 1.0:
            print(f"  ✓ Convergencia alcanzada")
            break
        
        Q = Q_nuevo
    
    # ------------------------------------------------
    # PASO 3: Capacidad nominal
    # ------------------------------------------------
    Pn = Fcr * props['seccion']['A'] / 1000  # kN
    Pn_LRFD = 0.90 * Pn  # kN
    
    print(f"\n{'='*50}")
    print(f"  RESULTADOS FINALES")
    print(f"{'='*50}")
    print(f"  Q final  : {Q:.4f}")
    print(f"  Fcr      : {Fcr:.2f} MPa")
    print(f"  Pn       : {Pn:.2f} kN")
    print(f"  φPn      : {Pn_LRFD:.2f} kN (LRFD)")
    print(f"{'='*50}\n")

else:
    print("\n✅ SECCIÓN COMPACTA/NO_COMPACTA → Q = 1.0")
    # Cálculo estándar sin Q...
```

---

## 5. CONSIDERACIONES IMPORTANTES

### Convergencia
- Típicamente converge en 2-3 iteraciones
- Usar tolerancia de 1% en Q
- Si no converge en 5 iteraciones → revisar datos

### Qa para almas
- Requiere **Fcr con Q=1.0** como primer paso
- La función `_calcular_qa_alma()` usa ancho efectivo simplificado
- Para mayor precisión: calcular Ae completo según AISC E7-16

### Límites de Qs
- **CRÍTICO**: 0.35 ≤ Qs ≤ 0.76
- Ya implementado en `calcular_Q()`
- Verificar que se aplique correctamente

### Casos especiales
- **Ángulos con b/t ≤ 20**: usar Fe de Ec. E3-4 (sin torsión)
- **Secciones asimétricas**: Fe según E4-6
- **Canales**: cuidado con eje de pandeo (puede ser torsional)

---

## 6. VALIDACIÓN

### Test con perfil conocido:
```python
# W12x65 con Fy=50 ksi (A36 no debería ser esbelta)
# Verificar que Q = 1.0

# HSS delgada con Fy alto (debería ser esbelta)
# Verificar que Q < 1.0 y Pn reduce correctamente
```

### Comparación con software comercial:
- SAP2000
- ETABS  
- Robot Structural Analysis

### Manual:
- Calcular Q a mano para un caso simple
- Verificar coincidencia hasta 4 decimales

---

## 7. REFERENCIAS

- **AISC 360-10**: Sección E7 (Members with Slender Elements)
- **CIRSOC 301**: Capítulo E7 (equivalente)
- **AISC Design Examples**: Version 14.1, Ejemplos con Q
