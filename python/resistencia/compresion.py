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
    ✅ Paso 7 : Pandeo global (Fe, Fcr)
    ✅ Paso 8 : Resistencia nominal y de diseño (Pn, Pd)

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
from clasificacion.clasificacion_seccion import clasificar_seccion


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
               Lz: float = None,
               Kx: float = 1.0,
               Ky: float = 1.0,
               Kz: float = 1.0,
               mostrar_calculo: bool = True) -> dict:
    """
    Calcular resistencia a compresión axial según CIRSOC 301 / AISC 360-10.

    Parámetros:
    -----------
    perfil_nombre  : str             — Designación (ej: 'W310x97', 'C15x50')
    Fy             : float           — Tensión de fluencia [MPa]
    Lx             : float           — Longitud de pandeo eje X [mm]
    Ly             : float           — Longitud de pandeo eje Y [mm]
    db_manager     : GestorBaseDatos — Instancia con la BD activa (CIRSOC o AISC)
    Lz             : float, opcional — Longitud pandeo torsional [mm]
                                       (default: max(Lx, Ly))
    Kx, Ky, Kz    : float           — Factores de longitud efectiva (default: 1.0)
    mostrar_calculo: bool            — Imprimir reporte en consola (default: True)

    Returns:
    --------
    dict — claves principales:
        'Pn'           [kN]   resistencia nominal
        'Pd'           [kN]   resistencia de diseño (φc·Pn)
        'Fcr'          [MPa]  tensión crítica
        'Fe'           [MPa]  tensión crítica elástica
        'modo_pandeo'  [str]  modo que gobierna
        'clase_seccion'[str]  COMPACTA | NO_COMPACTA | ESBELTA
        'esbeltez_max' [—]    máxima esbeltez KL/r
        'advertencias' [list]
    """

    # ================================================================== #
    # PASO 1: OBTENER DATOS DEL PERFIL                                   #
    # ================================================================== #

    perfil    = db_manager.obtener_datos_perfil(perfil_nombre)
    bd_nombre = db_manager.nombre_base_activa()
    tipo      = str(perfil['Tipo']).strip()

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

    # ================================================================== #
    # PASO 6: CLASIFICACIÓN DE SECCIÓN                                   #
    # ================================================================== #

    clasificacion = clasificar_seccion(props, Fy, E=E_ACERO, mostrar=mostrar_calculo)
    resultados['clasificacion']  = clasificacion
    resultados['clase_seccion']  = clasificacion['clase_seccion']
    resultados['advertencias'].extend(clasificacion['advertencias'])

    if clasificacion['es_esbelta']:
        resultados['advertencias'].append(
            "Sección ESBELTA: Ae no implementado, se usa Ag (resultado no conservador)."
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
        Fe           = min(modos_Fe.values())
        modo_governa = min(modos_Fe, key=modos_Fe.get)
        esbeltez_max = max(esbeltez_x, esbeltez_y)

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

    if mostrar_calculo:
        _imprimir_reporte(resultados)

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
    print(f"  Fy = {r['Fy']} MPa    E = {r['E']} MPa    Q = {r['Q']}")
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
