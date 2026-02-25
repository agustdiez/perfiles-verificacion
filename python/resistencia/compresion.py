"""
compresion.py
=============
Cálculo de resistencia a compresión axial según CIRSOC 301 / AISC 360-10.

Estado de implementación:
    ✅ Paso 1 : Obtener datos del perfil
    ✅ Paso 2 : Extraer propiedades geométricas
    ✅ Paso 3 : Ajustar Lz
    ✅ Paso 4 : Inicializar resultados
    ✅ Paso 5 : Asignar variables de trabajo
    ✅ Paso 6 : Clasificación de sección (λ vs λp/λr)
    ✅ Paso 7 : Cálculo de factor Q para secciones esbeltas (AISC E7)
    ✅ Paso 8 : Pandeo global (Fe, Fcr con Q)
    ✅ Paso 9 : Resistencia nominal y de diseño (Pn, Pd)

Requiere:
    core/gestor_base_datos.py
    core/utilidades_perfil.py
    clasificacion/clasificacion_seccion.py

Unidades internas : mm / mm² / mm⁴ / MPa / N
Unidades de salida: kN (fuerzas), MPa (tensiones), cm² (área en reporte)
"""

import numpy as np
import sys
import os

_raiz_python = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _raiz_python not in sys.path:
    sys.path.insert(0, _raiz_python)

from core.utilidades_perfil import extraer_propiedades, verificar_propiedades
from clasificacion.clasificacion_seccion import clasificar_seccion, calcular_Q


# ============================================================================
# CONSTANTES
# ============================================================================

E_ACERO = 200_000   # MPa
G_ACERO =  77_200   # MPa
PHI_C   =    0.90   # Factor de reducción LRFD compresión


# ============================================================================
# FUNCIONES DE Fe
# ============================================================================

def _fe_flexional(KL: float, r: float) -> tuple[float, float]:
    """Fe por pandeo flexional: π²·E / (KL/r)²  → (Fe [MPa], esbeltez)"""
    esbeltez = KL / r
    return np.pi**2 * E_ACERO / esbeltez**2, esbeltez


def _fe_torsional(J: float, Cw: float, Kz: float, Lz: float,
                  Ag: float, ro: float) -> float:
    """
    Fe por pandeo torsional puro (doble simetría).
    Fe_z = (π²·E·Cw / (Kz·Lz)² + G·J) / (Ag·ro²)
    Ref: AISC 360-10 E4-4
    """
    return (np.pi**2 * E_ACERO * Cw / (Kz * Lz)**2 + G_ACERO * J) / (Ag * ro**2)


def _fe_flexotorsional_canal(Fe_y: float, Fe_z: float, H: float) -> float:
    """
    Fe por pandeo flexo-torsional para canal (simetría en Y).
    Ref: AISC 360-10 E4, ec. E4-2
    """
    suma = Fe_y + Fe_z
    return suma / (2 * H) * (1 - np.sqrt(1 - 4 * Fe_y * Fe_z * H / suma**2))


def _calcular_Fcr(Fe: float, Fy: float, Q: float = 1.0) -> float:
    """
    Tensión crítica según AISC 360-10 E3/E7.
        Q·Fy/Fe ≤ 2.25 → Fcr = 0.658^(Q·Fy/Fe) · Q·Fy
        Q·Fy/Fe > 2.25 → Fcr = 0.877 · Fe
    """
    QFy   = Q * Fy
    ratio = QFy / Fe
    return (0.658 ** ratio) * QFy if ratio <= 2.25 else 0.877 * Fe


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def compresion(perfil_nombre: str,
               Fy: float,
               Lx: float,
               Ly: float,
               db_manager,
               tipo_perfil: str = None,
               Lz: float = None,
               Kx: float = 1.0,
               Ky: float = 1.0,
               Kz: float = 1.0,
               max_iter_Q: int = 5,
               tol_Q: float = 0.01,
               mostrar_calculo: bool = True) -> dict:
    """
    Calcular resistencia a compresión axial según CIRSOC 301 / AISC 360-10.
    Incluye cálculo iterativo del factor Q para secciones esbeltas (AISC E7).

    Parámetros:
    -----------
    perfil_nombre  : str             — Designación (ej: 'W310x97', 'C15x50', '100')
    Fy             : float           — Tensión de fluencia [MPa]
    Lx             : float           — Longitud de pandeo eje X [mm]
    Ly             : float           — Longitud de pandeo eje Y [mm]
    db_manager     : GestorBaseDatos — Instancia con la BD activa (CIRSOC o AISC)
    tipo_perfil    : str, opcional   — Tipo para búsqueda exacta (ej: 'IPE', 'IPN')
                                       Requerido si perfil_nombre es ambiguo
    Lz             : float, opcional — Longitud pandeo torsional [mm]
                                       (default: max(Lx, Ly))
    Kx, Ky, Kz     : float           — Factores de longitud efectiva (default: 1.0)
    max_iter_Q     : int             — Máx. iteraciones para convergencia de Q (default: 5)
    tol_Q          : float           — Tolerancia relativa para Q (default: 0.01 = 1%)
    mostrar_calculo: bool            — Imprimir reporte en consola (default: True)

    Returns:
    --------
    dict — claves principales:
        'Pn'            [kN]   resistencia nominal
        'Pd'            [kN]   resistencia de diseño (φc·Pn)
        'Fcr'           [MPa]  tensión crítica
        'Fe'            [MPa]  tensión crítica elástica
        'Q'             [—]    factor de reducción por elementos esbeltos
        'Qs'            [—]    factor para elementos no rigidizados
        'Qa'            [—]    factor para elementos rigidizados
        'iter_Q'        [int]  número de iteraciones realizadas para Q
        'modo_pandeo'   [str]  modo que gobierna
        'clase_seccion' [str]  COMPACTA | NO_COMPACTA | ESBELTA
        'esbeltez_max'  [—]    máxima esbeltez KL/r
        'advertencias'  [list]
    """

    # ================================================================== #
    # PASO 0: Inicio de LaTeX                                   #
    # ================================================================== #

    latex_doc = []
    latex_doc.append(f"\\section{{Cálculo de Compresión: {perfil_nombre}}}")
    

    # ================================================================== #
    # PASO 1: OBTENER DATOS DEL PERFIL                                   #
    # ================================================================== #

    perfil    = db_manager.obtener_datos_perfil(perfil_nombre, tipo=tipo_perfil)
    bd_nombre = db_manager.nombre_base_activa()
    tipo      = str(perfil['Tipo']).strip()
    latex_doc.append(f"\\text{{Base de datos: {bd_nombre}}}")

    # ================================================================== #
    # PASO 2: EXTRAER PROPIEDADES (todo en mm / mm² / mm⁴)               #
    # ================================================================== #

    props        = extraer_propiedades(perfil, base_datos=bd_nombre)
    familia      = props['familia']   # DOBLE_T | CANAL | ANGULAR | DESCONOCIDA
    verificacion = verificar_propiedades(props)

    if not verificacion['completo']:
        raise ValueError(
            f"Perfil '{perfil_nombre}' sin propiedades necesarias. "
            f"Faltantes: {', '.join(verificacion['faltantes'])}"
        )

    # ================================================================== #
    # PASO 3: AJUSTAR Lz                                                 #
    # ================================================================== #

    if Lz is None:
        Lz = max(Lx, Ly)

    # ================================================================== #
    # PASO 4: INICIALIZAR RESULTADOS                                     #
    # ================================================================== #

    resultados = {
        'perfil'      : perfil_nombre,
        'tipo'        : tipo,
        'familia'     : familia,
        'base_datos'  : bd_nombre,
        'Fy'          : Fy,
        'E'           : E_ACERO,
        'G'           : G_ACERO,
        'phi_c'       : PHI_C,
        'Q'           : 1.0,
        'Qs'          : 1.0,
        'Qa'          : 1.0,
        'iter_Q'      : 0,
        'Lx'          : Lx,
        'Ly'          : Ly,
        'Lz'          : Lz,
        'Kx'          : Kx,
        'Ky'          : Ky,
        'Kz'          : Kz,
        'advertencias': list(verificacion['advertencias']),
    }

    # ================================================================== #
    # PASO 5: VARIABLES DE TRABAJO (mm / mm² / mm⁴ / MPa)               #
    # ================================================================== #

    A  = props['basicas']['Ag']
    rx = props['flexion']['rx']
    ry = props['flexion']['ry']
    J  = props['torsion']['J']
    Cw = props['torsion']['Cw']
    xo = props['centro_corte']['xo']
    yo = props['centro_corte']['yo']
    ro = props['centro_corte']['ro']
    H  = props['centro_corte']['H']

    resultados.update({
        'propiedades': props,
        'A' : A,
        'rx': rx, 'ry': ry,
        'J' : J,  'Cw': Cw,
        'xo': xo, 'yo': yo, 'ro': ro,
    })

    latex_doc.append(f"A = {A/100:.2f} \\, \\text{{cm}}^2")
    latex_doc.append(f"r_x = {rx/10:.2f} \\, \\text{{cm}}, \\quad r_y = {ry/10:.2f} \\, \\text{{cm}}")
    latex_doc.append(f"r_o = {ro/10:.2f} \\, \\text{{cm}}")

    # ================================================================== #
    # PASO 6: CLASIFICACIÓN DE SECCIÓN                                   #
    # ================================================================== #

    clasificacion = clasificar_seccion(props, Fy, E=E_ACERO, mostrar=mostrar_calculo)
    resultados['clasificacion']  = clasificacion
    resultados['clase_seccion']  = clasificacion['clase_seccion']
    resultados['advertencias'].extend(clasificacion['advertencias'])

    # ================================================================== #
    # PASO 6.5: CÁLCULO DE FACTOR Q (solo si es ESBELTA)                #
    # ================================================================== #

    if clasificacion['es_esbelta']:
        latex_doc.append("\\subsection{Cálculo de Factor Q (Sección Esbelta)}")
        
        # Necesitamos calcular Fe primero para iniciar iteración
        # Calculamos Fe preliminar (se hará formalmente en PASO 7)
        KxLx = Kx * Lx
        KyLy = Ky * Ly
        
        if familia == 'DOBLE_T':
            Fe_x_temp, _ = _fe_flexional(KxLx, rx)
            Fe_y_temp, _ = _fe_flexional(KyLy, ry)
            Fe_z_temp = _fe_torsional(J, Cw, Kz, Lz, A, ro)
            Fe_temp = min(Fe_x_temp, Fe_y_temp, Fe_z_temp)
        elif familia == 'CANAL':
            Fe_x_temp, _ = _fe_flexional(KxLx, rx)
            Fe_y_temp, _ = _fe_flexional(KyLy, ry)
            Fe_z_temp = _fe_torsional(J, Cw, Kz, Lz, A, ro)
            if H is not None and H > 0 and xo > 0:
                Fe_yzt_temp = _fe_flexotorsional_canal(Fe_y_temp, Fe_z_temp, H)
            else:
                Fe_yzt_temp = Fe_y_temp
            Fe_temp = min(Fe_x_temp, Fe_yzt_temp)
        elif familia == 'ANGULAR':
            iv = props['flexion']['iv']
            KL_angular = max(KxLx, KyLy, Kz * Lz)
            Fe_temp, _ = _fe_flexional(KL_angular, iv)
        else:
            Fe_temp = 1000  # Valor por defecto si no reconoce familia
        
        # Iteración para calcular Q
        Q_actual = 1.0
        iter_Q = 0
        
        for iter_Q in range(1, max_iter_Q + 1):
            # Calcular Fcr con Q actual
            Fcr_temporal = _calcular_Fcr(Fe_temp, Fy, Q=Q_actual)
            
            # Calcular nuevo Q usando Fcr temporal
            Q_info = calcular_Q(props, Fy, E_ACERO, Fcr=Fcr_temporal)
            Q_nuevo = Q_info['Q']
            Qs = Q_info['Qs']
            Qa = Q_info['Qa']
            
            # Verificar convergencia
            error_relativo = abs(Q_nuevo - Q_actual) / Q_actual if Q_actual > 0 else 1.0
            
            latex_doc.append(
                f"\\text{{Iter. {iter_Q}: }} Q = {Q_nuevo:.4f} "
                f"(Q_s = {Qs:.4f}, Q_a = {Qa:.4f}), "
                f"F_{{cr}} = {Fcr_temporal:.2f} \\, \\text{{MPa}}, "
                f"\\epsilon = {error_relativo*100:.2f}\\%"
            )
            
            if error_relativo < tol_Q:
                break
            
            Q_actual = Q_nuevo
        
        # Advertencia sobre convergencia
        if error_relativo < tol_Q:
            resultados['advertencias'].append(
                f"Factor Q convergió en {iter_Q} iteraciones: Q = {Q_nuevo:.4f} "
                f"(Qs = {Qs:.4f}, Qa = {Qa:.4f})"
            )
        else:
            resultados['advertencias'].append(
                f"ADVERTENCIA: Factor Q no convergió en {max_iter_Q} iteraciones. "
                f"Último valor: Q = {Q_nuevo:.4f}"
            )
        
        # Actualizar resultados con Q final
        resultados['Q'] = Q_nuevo
        resultados['Qs'] = Qs
        resultados['Qa'] = Qa
        resultados['iter_Q'] = iter_Q
        resultados['Q_notas'] = Q_info['notas']
        
        latex_doc.append(
            f"Q_{{\\text{{final}}}} = Q_s \\times Q_a = "
            f"{Qs:.4f} \\times {Qa:.4f} = {Q_nuevo:.4f}"
        )
        
    else:
        latex_doc.append("\\text{Sección COMPACTA/NO\\_COMPACTA: } Q = 1.0")
        resultados['advertencias'].append(
            f"Sección {clasificacion['clase_seccion']}: Q = 1.0 (sin reducción)"
        )

    # ================================================================== #
    # PASO 7: PANDEO GLOBAL                                              #
    # ================================================================== #
    #
    # Modos según familia (AISC 360-10):
    #   DOBLE_T → flexional X, flexional Y, torsional puro   → min(Fe_x, Fe_y, Fe_z)
    #   CANAL   → flexional X, flexo-torsional YZ            → min(Fe_x, Fe_yzt)
    #   ANGULAR → flexional eje principal menor (iv)         → Fe_iv
    # ================================================================== #

    KxLx = Kx * Lx
    KyLy = Ky * Ly
    modos_Fe = {}

    # ------------------------------------------------------------------ #
    # DOBLE T                                                             #
    # ------------------------------------------------------------------ #
    if familia == 'DOBLE_T':

        Fe_x, esbeltez_x = _fe_flexional(KxLx, rx)
        Fe_y, esbeltez_y = _fe_flexional(KyLy, ry)
        Fe_z             = _fe_torsional(J, Cw, Kz, Lz, A, ro)

        modos_Fe = {
            'Flexional_X': Fe_x,
            'Flexional_Y': Fe_y,
            'Torsional_Z': Fe_z,
        }
        latex_doc.append(f"\\lambda_x = \\frac{{K_x L_x}}{{r_x}} = \\frac{{{Kx} \\times {Lx}}}{{{rx:.2f}}} = {esbeltez_x:.2f}")
        latex_doc.append(f"F_{{e,x}} = \\frac{{\\pi^2 E}}{{\\lambda_x^2}} = \\frac{{\\pi^2 \\times {E_ACERO}}}{{{esbeltez_x:.2f}^2}} = {Fe_x:.2f} \\, \\text{{MPa}}")
        
        latex_doc.append(f"\\lambda_y = {esbeltez_y:.2f}")
        latex_doc.append(f"F_{{e,y}} = {Fe_y:.2f} \\, \\text{{MPa}}")
        
        latex_doc.append(f"F_{{e,z}} = \\frac{{\\pi^2 E C_w}}{{(K_z L_z)^2}} + \\frac{{G J}}{{A_g r_o^2}} = {Fe_z:.2f} \\, \\text{{MPa}}")

        Fe           = min(modos_Fe.values())
        modo_governa = min(modos_Fe, key=modos_Fe.get)
        esbeltez_max = max(esbeltez_x, esbeltez_y)
        latex_doc.append(f"F_e = \\min(F_{{e,x}}, F_{{e,y}}, F_{{e,z}}) = {Fe:.2f} \\, \\text{{MPa}} \\quad (\\text{{{modo_governa}}})")

    # ------------------------------------------------------------------ #
    # CANAL                                                               #
    # ------------------------------------------------------------------ #
    elif familia == 'CANAL':

        Fe_x, esbeltez_x = _fe_flexional(KxLx, rx)
        Fe_y, esbeltez_y = _fe_flexional(KyLy, ry)
        Fe_z             = _fe_torsional(J, Cw, Kz, Lz, A, ro)

        # H ya calculado en extraer_propiedades — no recalcular
        if H is not None and H > 0 and xo > 0:
            Fe_yzt = _fe_flexotorsional_canal(Fe_y, Fe_z, H)
        else:
            Fe_yzt = Fe_y
            resultados['advertencias'].append(
                "xo/H no disponibles — pandeo flexo-torsional calculado con Fe_y (conservador)."
            )

        modos_Fe = {
            'Flexional_X'       : Fe_x,
            'Flexo_torsional_YZ': Fe_yzt,
        }
        Fe           = min(modos_Fe.values())
        modo_governa = min(modos_Fe, key=modos_Fe.get)
        esbeltez_max = max(esbeltez_x, esbeltez_y)

        # Intermedios útiles para trazabilidad
        resultados.update({
            'Fe_z': round(Fe_z, 2),
            'Fe_y': round(Fe_y, 2),
            'H'   : round(H, 4) if H is not None else None,
        })

    # ------------------------------------------------------------------ #
    # ANGULAR                                                             #
    # ------------------------------------------------------------------ #
    elif familia == 'ANGULAR':

        iv            = props['flexion']['iv']
        KL_angular    = max(KxLx, KyLy, Kz * Lz)
        Fe_iv, esb_iv = _fe_flexional(KL_angular, iv)

        modos_Fe     = {'Flexional_iv': Fe_iv}
        Fe           = Fe_iv
        modo_governa = 'Flexional_iv'
        esbeltez_max = esb_iv

    else:
        raise ValueError(
            f"Familia '{familia}' no implementada en pandeo global. "
            f"Tipos soportados: DOBLE_T, CANAL, ANGULAR."
        )

    # Verificación límite esbeltez KL/r ≤ 200 (CIRSOC 301)
    if esbeltez_max > 200:
        resultados['advertencias'].append(
            f"Esbeltez KL/r = {esbeltez_max:.1f} supera el límite de 200 (CIRSOC 301)."
        )

    resultados.update({
        'modos_Fe'    : {k: round(v, 2) for k, v in modos_Fe.items()},
        'Fe'          : round(Fe, 2),
        'modo_pandeo' : modo_governa,
        'esbeltez_x'  : round(KxLx / rx, 2),
        'esbeltez_y'  : round(KyLy / ry, 2),
        'esbeltez_max': round(esbeltez_max, 2),
    })

    # ================================================================== #
    # PASO 8: Fcr, Pn, Pd                                                #
    # ================================================================== #

    Fcr = _calcular_Fcr(Fe, Fy, Q=resultados['Q'])
    Pn  = Fcr * A          # N
    Pd  = PHI_C * Pn       # N

    resultados.update({
        'Fcr': round(Fcr, 2),
        'Pn' : round(Pn / 1000, 2),   # kN
        'Pd' : round(Pd / 1000, 2),   # kN
    })

    ratio = resultados['Q'] * Fy / Fe
    if ratio <= 2.25:
        latex_doc.append(f"\\frac{{Q F_y}}{{F_e}} = {ratio:.3f} \\leq 2.25 \\rightarrow F_{{cr}} = 0.658^{{{ratio:.3f}}} \\times {Fy} = {Fcr:.2f} \\, \\text{{MPa}}")
    else:
        latex_doc.append(f"\\frac{{Q F_y}}{{F_e}} = {ratio:.3f} > 2.25 \\rightarrow F_{{cr}} = 0.877 \\times F_e = {Fcr:.2f} \\, \\text{{MPa}}")
    
    latex_doc.append(f"P_n = F_{{cr}} \\times A_g = {Fcr:.2f} \\times {A/100:.2f} = {Pn/1000:.2f} \\, \\text{{kN}}")
    latex_doc.append(f"P_d = \\phi_c P_n = {PHI_C} \\times {Pn/1000:.2f} = {Pd/1000:.2f} \\, \\text{{kN}}")

    if mostrar_calculo:
        _imprimir_reporte(resultados)

    #Sumo la columna de latex
    resultados['latex'] = '\n\n'.join(latex_doc)
    return resultados


# ============================================================================
# REPORTE EN CONSOLA
# ============================================================================

def _imprimir_reporte(r: dict):
    """Imprimir resumen del cálculo. Magnitudes en unidades CIRSOC donde aplica."""

    # Convertir A a cm² y ro a cm para display
    A_cm2 = r['A'] / 100
    ro_cm = r['ro'] / 10

    print()
    print("=" * 62)
    print("  COMPRESIÓN AXIAL — CIRSOC 301 / AISC 360-10")
    print("=" * 62)
    print(f"  Perfil     : {r['perfil']}   ({r['tipo']} — {r['familia']})")
    print(f"  Base datos : {r['base_datos']}")
    print(f"  Fy = {r['Fy']} MPa    E = {r['E']} MPa")
    
    # Mostrar Q solo si es diferente de 1.0
    if r['Q'] < 1.0:
        print(f"  Q = {r['Q']:.4f}  (Qs = {r['Qs']:.4f}, Qa = {r['Qa']:.4f})  "
              f"← {r['iter_Q']} iter.")
    
    print(f"  Lx = {r['Lx']:.0f} mm   Ly = {r['Ly']:.0f} mm   Lz = {r['Lz']:.0f} mm")
    print(f"  Kx = {r['Kx']}   Ky = {r['Ky']}   Kz = {r['Kz']}")
    print("-" * 62)
    print(f"  Propiedades")
    print(f"    A  = {A_cm2:.2f} cm²    rx = {r['rx']/10:.2f} cm    ry = {r['ry']/10:.2f} cm")
    print(f"    ro = {ro_cm:.2f} cm     Clase sección: {r['clase_seccion']}")
    print("-" * 62)
    print(f"  Esbelteces : KLx/rx = {r['esbeltez_x']:.1f}   "
          f"KLy/ry = {r['esbeltez_y']:.1f}   máx = {r['esbeltez_max']:.1f}")
    print("-" * 62)
    print(f"  {'Modo de pandeo':<28} {'Fe [MPa]':>10}")
    print("-" * 62)
    for modo, fe_val in r['modos_Fe'].items():
        marca = "  ← gobierna" if modo == r['modo_pandeo'] else ""
        print(f"  {modo:<28} {fe_val:>10.2f}{marca}")
    print("-" * 62)
    print(f"  Fe  = {r['Fe']:.2f} MPa  ({r['modo_pandeo']})")
    print(f"  Fcr = {r['Fcr']:.2f} MPa")
    print(f"  Pn  = {r['Pn']:.1f} kN")
    print(f"  Pd  = φc·Pn = {r['phi_c']} × {r['Pn']:.1f} = {r['Pd']:.1f} kN")
    print("=" * 62)

    for adv in r['advertencias']:
        print(f"  ⚠️   {adv}")
    if r['advertencias']:
        print()


# ============================================================================
# BLOQUE DE PRUEBA
# ============================================================================

if __name__ == '__main__':

    from core.gestor_base_datos import GestorBaseDatos

    db = GestorBaseDatos()

    print("\n" + "=" * 62)
    print("  TEST CIRSOC")
    print("=" * 62)
    db.cambiar_base('CIRSOC')

    print("\n--- Doble T ---")
    r1 = compresion('18x97', Fy=250, Lx=5000, Ly=5000, db_manager=db)
    print(r1['latex'])

    print("\n--- Canal ---")
    r2 = compresion('C15x50', Fy=250, Lx=3000, Ly=3000, db_manager=db)

    print("\n--- Angular ---")
    r3 = compresion('L 4 x 4 x 1/2', Fy=250, Lx=2000, Ly=2000, db_manager=db)

    print("\n" + "=" * 62)
    print("  TEST AISC")
    print("=" * 62)
    db.cambiar_base('AISC')

    print("\n--- Doble T ---")
    r4 = compresion('W18X97', Fy=250, Lx=5000, Ly=5000, db_manager=db)

    print("\n--- Canal ---")
    r5 = compresion('C15X50', Fy=250, Lx=3000, Ly=3000, db_manager=db)
