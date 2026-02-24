"""
clasificacion_seccion.py
========================
Clasificación de secciones transversales para flexocompresión
según CIRSOC 301 / AISC 360-10 — Tabla B4.1

Clasificaciones posibles:
    COMPACTA    : todos los elementos cumplen λ ≤ λp
    NO_COMPACTA : algún elemento tiene λp < λ ≤ λr  (ninguno supera λr)
    ESBELTA     : algún elemento tiene λ > λr

Tipos de perfil soportados:
    Doble T : W, M, HP, IPE, IPN, IPB, IPBl, IPBv
    Canal   : C, MC, UPN
    Angular : L
"""

import numpy as np


# ============================================================================
# LÍMITES λp y λr  (CIRSOC 301 / AISC 360-10, Tabla B4.1)
# ============================================================================

def _limites_ala_doble_t(E: float, Fy: float) -> tuple[float, float]:
    """
    Ala de perfil doble T.
    Elemento voladizo (un lado desde el alma).  λ = bf / (2·tf)
    Ref: AISC 360-10 Tabla B4.1, caso 1
    """
    raiz = np.sqrt(E / Fy)
    return 0.38 * raiz, 1.00 * raiz


def _limites_alma_doble_t(E: float, Fy: float) -> tuple[float, float]:
    """
    Alma de perfil doble T.
    Elemento interior sujeto en ambos bordes.  λ = hw / tw
    Ref: AISC 360-10 Tabla B4.1, caso 9
    """
    raiz = np.sqrt(E / Fy)
    return 3.76 * raiz, 5.70 * raiz


def _limites_ala_canal(E: float, Fy: float) -> tuple[float, float]:
    """
    Ala de perfil canal.
    Voladizo desde el alma.  λ = bf / tf  (BD CIRSOC: columna bf/2tf)
    Ref: AISC 360-10 Tabla B4.1, caso 1
    """
    raiz = np.sqrt(E / Fy)
    return 0.38 * raiz, 1.00 * raiz


def _limites_alma_canal(E: float, Fy: float) -> tuple[float, float]:
    """
    Alma de perfil canal.  λ = hw / tw
    Ref: AISC 360-10 Tabla B4.1, caso 9
    """
    raiz = np.sqrt(E / Fy)
    return 3.76 * raiz, 5.70 * raiz


def _limites_pata_angular(E: float, Fy: float) -> tuple[float, float]:
    """
    Pata de perfil angular. Voladizo libre.  λ = b / t
    λp conservador = 0.38·√(E/Fy).  λr = 0.45·√(E/Fy)
    Ref: AISC 360-10 Tabla B4.1, caso 3
    """
    raiz = np.sqrt(E / Fy)
    return 0.38 * raiz, 0.45 * raiz


# ============================================================================
# CLASIFICACIÓN DE UN ELEMENTO INDIVIDUAL
# ============================================================================

def _clasificar_elemento(nombre: str, lambda_val: float,
                          lambda_p: float | None, lambda_r: float) -> dict:
    """
    Clasificar un elemento de la sección.

    Returns dict: 'nombre', 'lambda', 'lambda_p', 'lambda_r', 'clase'
    """
    if lambda_p is not None and lambda_val <= lambda_p:
        clase = 'COMPACTA'
    elif lambda_val <= lambda_r:
        clase = 'NO_COMPACTA'
    else:
        clase = 'ESBELTA'

    return {
        'nombre'  : nombre,
        'lambda'  : round(lambda_val, 3),
        'lambda_p': round(lambda_p, 3) if lambda_p is not None else None,
        'lambda_r': round(lambda_r, 3),
        'clase'   : clase,
    }


# ============================================================================
# CLASIFICACIÓN DE SECCIÓN COMPLETA
# ============================================================================

def clasificar_seccion(props: dict, Fy: float,
                       E: float = 200_000,
                       mostrar: bool = True) -> dict:
    """
    Clasificar la sección transversal para flexocompresión.

    Parámetros:
    -----------
    props   : dict  — salida de extraer_propiedades() en core/utilidades_perfil.py
    Fy      : float — tensión de fluencia [MPa]
    E       : float — módulo de elasticidad [MPa] (default: 200 000)
    mostrar : bool  — imprimir reporte en consola

    Returns:
    --------
    dict:
        'elementos'    : dict
        'clase_seccion': 'COMPACTA' | 'NO_COMPACTA' | 'ESBELTA'
        'es_esbelta'   : bool
        'advertencias' : list[str]
    """
    tipo         = props['tipo']
    elementos    = {}
    advertencias = []

    # ------------------------------------------------------------------ #
    # DOBLE T                                                             #
    # ------------------------------------------------------------------ #
    if tipo in ['W', 'M', 'HP', 'IPE', 'IPN', 'IPB', 'IPBl', 'IPBv']:

        lp, lr = _limites_ala_doble_t(E, Fy)
        elementos['ala'] = _clasificar_elemento(
            'Ala (bf/2tf)', props['seccion']['bf_2tf'], lp, lr
        )
        lp, lr = _limites_alma_doble_t(E, Fy)
        elementos['alma'] = _clasificar_elemento(
            'Alma (hw/tw)', props['seccion']['hw_tw'], lp, lr
        )

    # ------------------------------------------------------------------ #
    # CANAL                                                               #
    # ------------------------------------------------------------------ #
    elif tipo in ['C', 'MC', 'UPN']:

        lp, lr = _limites_ala_canal(E, Fy)
        elementos['ala'] = _clasificar_elemento(
            'Ala (bf/tf)', props['seccion']['bf_2tf'], lp, lr
        )
        lp, lr = _limites_alma_canal(E, Fy)
        elementos['alma'] = _clasificar_elemento(
            'Alma (hw/tw)', props['seccion']['hw_tw'], lp, lr
        )

    # ------------------------------------------------------------------ #
    # ANGULAR                                                             #
    # ------------------------------------------------------------------ #
    elif tipo == 'L':

        lp, lr = _limites_pata_angular(E, Fy)
        elementos['pata'] = _clasificar_elemento(
            'Pata (b/t)', props['seccion']['b_t'], lp, lr
        )
        advertencias.append(
            "Ángulo: λp adoptado conservadoramente igual al de ala de doble T "
            "(0.38·√(E/Fy)). Verificar aplicabilidad según caso de carga."
        )

    else:
        raise ValueError(
            f"Tipo '{tipo}' no soportado. "
            f"Válidos: W, M, HP, IPE, IPN, IPB, IPBl, IPBv, C, MC, UPN, L."
        )

    # Clase global
    clases = [el['clase'] for el in elementos.values()]
    if 'ESBELTA' in clases:
        clase_seccion = 'ESBELTA'
    elif 'NO_COMPACTA' in clases:
        clase_seccion = 'NO_COMPACTA'
    else:
        clase_seccion = 'COMPACTA'

    if mostrar:
        _imprimir_clasificacion(tipo, elementos, clase_seccion, Fy, E, advertencias)

    return {
        'elementos'    : elementos,
        'clase_seccion': clase_seccion,
        'es_esbelta'   : clase_seccion == 'ESBELTA',
        'advertencias' : advertencias,
    }


# ============================================================================
# REPORTE EN CONSOLA
# ============================================================================

def _imprimir_clasificacion(tipo, elementos, clase_seccion, Fy, E, advertencias):

    iconos = {'COMPACTA': '✅', 'NO_COMPACTA': '⚠️', 'ESBELTA': '❌'}

    print("=" * 60)
    print("  CLASIFICACIÓN DE SECCIÓN — CIRSOC 301 / AISC 360-10")
    print("=" * 60)
    print(f"  Tipo : {tipo}    Fy = {Fy} MPa    E = {E} MPa")
    print("-" * 60)
    print(f"  {'Elemento':<20} {'λ':>8} {'λp':>8} {'λr':>8}  Clase")
    print("-" * 60)

    for el in elementos.values():
        lp_str = f"{el['lambda_p']:.2f}" if el['lambda_p'] is not None else "  N/A "
        print(
            f"  {el['nombre']:<20} "
            f"{el['lambda']:>8.2f} "
            f"{lp_str:>8} "
            f"{el['lambda_r']:>8.2f}  "
            f"{iconos[el['clase']]} {el['clase']}"
        )

    print("=" * 60)
    print(f"  {iconos[clase_seccion]}  CLASE DE SECCIÓN: {clase_seccion}")
    print("=" * 60)

    for adv in advertencias:
        print(f"  ⚠️  {adv}")
    if advertencias:
        print()
