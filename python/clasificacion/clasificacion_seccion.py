"""
clasificacion_seccion.py
========================
Clasificación de secciones transversales para flexocompresión
según CIRSOC 301 / AISC 360-10 — Tabla B4.1

Incluye cálculo del factor Q para secciones esbeltas según AISC 360-10 Sección E7.

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
# FACTOR Q PARA ELEMENTOS ESBELTOS (AISC 360-10 Sección E7)
# ============================================================================

def _calcular_qs_ala_laminada(bt_ratio: float, E: float, Fy: float) -> float:
    """
    Qs para alas de perfiles laminados (rolled) - AISC E7 Ec. E7-4 a E7-6
    Elementos no rigidizados: alas proyectadas desde columnas laminadas
    
    b/t para doble T = bf/(2tf)
    b/t para canal = bf/tf
    """
    raiz_E_Fy = np.sqrt(E / Fy)
    
    if bt_ratio <= 0.56 * raiz_E_Fy:
        return 1.0
    elif bt_ratio < 1.03 * raiz_E_Fy:
        return 1.415 - 0.74 * bt_ratio * np.sqrt(Fy / E)
    else:
        return 0.69 * E / (Fy * bt_ratio**2)


def _calcular_qs_angular(bt_ratio: float, E: float, Fy: float) -> float:
    """
    Qs para ángulos simples - AISC E7 Ec. E7-10 a E7-12
    b/t = b/t (pata completa)
    """
    raiz_E_Fy = np.sqrt(E / Fy)
    
    if bt_ratio <= 0.45 * raiz_E_Fy:
        return 1.0
    elif bt_ratio <= 0.91 * raiz_E_Fy:
        return 1.34 - 0.76 * bt_ratio * np.sqrt(Fy / E)
    else:
        return 0.53 * E / (Fy * bt_ratio**2)


def _calcular_qa_alma(hw_tw: float, E: float, Fcr: float, 
                      b: float, A_total: float) -> float:
    """
    Qa para almas de doble T y canales - AISC E7 Ec. E7-16, E7-17
    Elementos rigidizados uniformemente comprimidos
    
    Parámetros:
    -----------
    hw_tw  : relación altura/espesor del alma
    E      : módulo de elasticidad [MPa]
    Fcr    : tensión crítica calculada con Q=1.0 [MPa]
    b      : ancho del alma (hw) [mm]
    A_total: área total de la sección [mm²]
    
    Returns:
    --------
    Qa : factor de reducción para elemento rigidizado esbelta
    """
    raiz_E_f = np.sqrt(E / Fcr)
    
    # Verificar si el alma es esbelta
    if hw_tw < 1.49 * raiz_E_f:
        return 1.0
    
    # Calcular ancho efectivo be (AISC E7-17)
    # be = b [1 - 0.34√(E/f) / (b/t)] √(E/f) / (b/t)
    factor = raiz_E_f / hw_tw
    be = b * (1.0 - 0.34 * factor) * factor
    
    # Limitar be ≤ b
    be = min(be, b)
    
    # Qa = Ae / Ag donde Ae se calcula con ancho efectivo
    # Para simplificación: Ae ≈ A_total - (b - be) × tw
    # Como no tenemos tw directamente, aproximamos: Qa ≈ be/b
    Qa = be / b
    
    return Qa


def calcular_Q(props: dict, Fy: float, E: float = 200_000,
               Fcr: float = None) -> dict:
    """
    Calcular factor de reducción Q para secciones con elementos esbeltos.
    Según AISC 360-10 Sección E7.
    
    Q = Qs × Qa donde:
        Qs: factor para elementos no rigidizados (unstiffened)
        Qa: factor para elementos rigidizados (stiffened)
    
    Parámetros:
    -----------
    props : dict — salida de extraer_propiedades()
    Fy    : float — tensión de fluencia [MPa]
    E     : float — módulo de elasticidad [MPa]
    Fcr   : float — tensión crítica con Q=1.0 [MPa] (requerido para Qa)
    
    Returns:
    --------
    dict:
        'Q'     : float  — factor total de reducción
        'Qs'    : float  — factor para elementos no rigidizados
        'Qa'    : float  — factor para elementos rigidizados
        'notas' : list[str] — observaciones del cálculo
    """
    tipo = props['tipo']
    Qs = 1.0
    Qa = 1.0
    notas = []
    
    # Clasificar primero para saber si es esbelta
    clasificacion = clasificar_seccion(props, Fy, E, mostrar=False)
    
    if not clasificacion['es_esbelta']:
        notas.append("Sección no esbelta: Q = 1.0")
        return {'Q': 1.0, 'Qs': 1.0, 'Qa': 1.0, 'notas': notas}
    
    # ------------------------------------------------------------------ #
    # DOBLE T                                                             #
    # ------------------------------------------------------------------ #
    if tipo in ['W', 'M', 'HP', 'IPE', 'IPN', 'IPB', 'IPBl', 'IPBv']:
        
        # Ala: elemento no rigidizado
        if clasificacion['elementos']['ala']['clase'] == 'ESBELTA':
            bt_ala = props['seccion']['bf_2tf']
            Qs = _calcular_qs_ala_laminada(bt_ala, E, Fy)
            notas.append(f"Ala esbelta: bf/2tf = {bt_ala:.2f}, Qs = {Qs:.4f}")
        
        # Alma: elemento rigidizado
        if clasificacion['elementos']['alma']['clase'] == 'ESBELTA':
            if Fcr is None:
                notas.append("ADVERTENCIA: Fcr no proporcionado, Qa = 1.0 (conservador)")
            else:
                hw_tw = props['seccion']['hw_tw']
                hw = props['geometria']['h'] - 2 * props['geometria']['tf']
                A_total = props['seccion']['A']
                Qa = _calcular_qa_alma(hw_tw, E, Fcr, hw, A_total)
                notas.append(f"Alma esbelta: hw/tw = {hw_tw:.2f}, Qa = {Qa:.4f}")
    
    # ------------------------------------------------------------------ #
    # CANAL                                                               #
    # ------------------------------------------------------------------ #
    elif tipo in ['C', 'MC', 'UPN']:
        
        # Ala: elemento no rigidizado
        if clasificacion['elementos']['ala']['clase'] == 'ESBELTA':
            bt_ala = props['seccion']['bf_2tf']
            Qs = _calcular_qs_ala_laminada(bt_ala, E, Fy)
            notas.append(f"Ala esbelta: bf/tf = {bt_ala:.2f}, Qs = {Qs:.4f}")
        
        # Alma: elemento rigidizado
        if clasificacion['elementos']['alma']['clase'] == 'ESBELTA':
            if Fcr is None:
                notas.append("ADVERTENCIA: Fcr no proporcionado, Qa = 1.0 (conservador)")
            else:
                hw_tw = props['seccion']['hw_tw']
                hw = props['geometria']['h'] - 2 * props['geometria']['tf']
                A_total = props['seccion']['A']
                Qa = _calcular_qa_alma(hw_tw, E, Fcr, hw, A_total)
                notas.append(f"Alma esbelta: hw/tw = {hw_tw:.2f}, Qa = {Qa:.4f}")
    
    # ------------------------------------------------------------------ #
    # ANGULAR                                                             #
    # ------------------------------------------------------------------ #
    elif tipo == 'L':
        
        if clasificacion['elementos']['pata']['clase'] == 'ESBELTA':
            bt = props['seccion']['b_t']
            Qs = _calcular_qs_angular(bt, E, Fy)
            notas.append(f"Pata esbelta: b/t = {bt:.2f}, Qs = {Qs:.4f}")
    
    else:
        raise ValueError(f"Tipo '{tipo}' no soportado.")
    
    # Limitar Qs según AISC: 0.35 ≤ Qs ≤ 0.76
    if Qs < 0.35:
        notas.append(f"Qs limitado de {Qs:.4f} a 0.35")
        Qs = 0.35
    elif Qs > 0.76:
        notas.append(f"Qs limitado de {Qs:.4f} a 0.76")
        Qs = 0.76
    
    Q = Qs * Qa
    
    return {
        'Q': Q,
        'Qs': Qs,
        'Qa': Qa,
        'notas': notas
    }


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
                       mostrar: bool = True,
                       calcular_q: bool = False,
                       Fcr: float = None) -> dict:
    """
    Clasificar la sección transversal para flexocompresión.

    Parámetros:
    -----------
    props      : dict  — salida de extraer_propiedades() en core/utilidades_perfil.py
    Fy         : float — tensión de fluencia [MPa]
    E          : float — módulo de elasticidad [MPa] (default: 200 000)
    mostrar    : bool  — imprimir reporte en consola
    calcular_q : bool  — calcular factor Q si es esbelta
    Fcr        : float — tensión crítica con Q=1.0 [MPa] (para calcular Qa)

    Returns:
    --------
    dict:
        'elementos'    : dict
        'clase_seccion': 'COMPACTA' | 'NO_COMPACTA' | 'ESBELTA'
        'es_esbelta'   : bool
        'advertencias' : list[str]
        'Q_info'       : dict (si calcular_q=True y es_esbelta=True)
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

    resultado = {
        'elementos'    : elementos,
        'clase_seccion': clase_seccion,
        'es_esbelta'   : clase_seccion == 'ESBELTA',
        'advertencias' : advertencias,
    }

    # Calcular Q si se solicita y la sección es esbelta
    if calcular_q and clase_seccion == 'ESBELTA':
        Q_info = calcular_Q(props, Fy, E, Fcr)
        resultado['Q_info'] = Q_info

    if mostrar:
        _imprimir_clasificacion(tipo, elementos, clase_seccion, Fy, E, advertencias)
        if calcular_q and clase_seccion == 'ESBELTA':
            _imprimir_factor_Q(Q_info)

    return resultado


# ============================================================================
# REPORTES EN CONSOLA
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


def _imprimir_factor_Q(Q_info: dict):
    """Imprimir reporte del factor Q"""
    print("=" * 60)
    print("  FACTOR Q — REDUCCIÓN POR ELEMENTOS ESBELTOS (AISC E7)")
    print("=" * 60)
    print(f"  Qs (no rigidizados) : {Q_info['Qs']:.4f}")
    print(f"  Qa (rigidizados)    : {Q_info['Qa']:.4f}")
    print(f"  Q = Qs × Qa         : {Q_info['Q']:.4f}")
    print("-" * 60)
    for nota in Q_info['notas']:
        print(f"  • {nota}")
    print("=" * 60)
    print()
