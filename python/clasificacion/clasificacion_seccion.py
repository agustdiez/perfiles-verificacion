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
    Doble T       : W, M, HP, S, IPE, IPN, IPB, IPBl, IPBv
    Canal         : C, MC, UPN
    Angular       : L
    Perfil T      : T, WT, MT, ST
    Tubo Circular : TUBO CIRC., PIPE
    Tubo Cuadrado : TUBO CUAD., HSS (cuadrado)
    Tubo Rect.    : TUBO RECT., HSS (rectangular)
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


def _limites_ala_perfil_t(E: float, Fy: float) -> tuple[float, float]:
    """
    Ala de perfil T (WT, MT, ST, T).
    Voladizo desde el alma.  λ = bf / (2·tf)
    Ref: AISC 360-10 Tabla B4.1a, caso 1 (compresión)
    """
    raiz = np.sqrt(E / Fy)
    return 0.38 * raiz, 1.00 * raiz


def _limites_alma_perfil_t(E: float, Fy: float) -> tuple[float, float]:
    """
    Alma de perfil T (stem).  λ = d / tw
    Ref: AISC 360-10 Tabla B4.1a, caso 4
    """
    raiz = np.sqrt(E / Fy)
    # Compresión: λr = 0.75·√(E/Fy) según caso 4
    # No hay λp para stem en compresión (solo λr)
    return None, 0.75 * raiz


def _limites_tubo_circular(E: float, Fy: float) -> tuple[float, float]:
    """
    Tubo circular (PIPE, TUBO CIRC.).  λ = D / t
    Ref: AISC 360-10 Tabla B4.1a, caso 9 (compresión)
    """
    raiz = np.sqrt(E / Fy)
    # Compresión: λr = 0.11·E/Fy
    # No hay λp para tubos circulares en compresión
    return None, 0.11 * (E / Fy)


def _limites_tubo_rectangular_pared(E: float, Fy: float) -> tuple[float, float]:
    """
    Paredes de tubo rectangular/cuadrado (HSS, TUBO CUAD., TUBO RECT.).
    λ = b / t  (para flanges)
    λ = h / t  (para webs)
    Ref: AISC 360-10 Tabla B4.1a, caso 6 (compresión)
    """
    raiz = np.sqrt(E / Fy)
    # Compresión: λr = 1.40·√(E/Fy)
    # No hay λp para HSS en compresión
    return None, 1.40 * raiz


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


def _calcular_qs_stem_perfil_t(dt_ratio: float, E: float, Fy: float) -> float:
    """
    Qs para stem (alma) de perfiles T - AISC E7 Ec. E7-7 a E7-9
    d/t = d/tw (altura del stem / espesor)
    """
    raiz_E_Fy = np.sqrt(E / Fy)
    
    if dt_ratio <= 0.75 * raiz_E_Fy:
        return 1.0
    elif dt_ratio <= 1.03 * raiz_E_Fy:
        return 1.908 - 1.22 * dt_ratio * np.sqrt(Fy / E)
    else:
        return 0.69 * E / (Fy * dt_ratio**2)


def _calcular_q_tubo_circular(Dt_ratio: float, E: float, Fy: float) -> float:
    """
    Q para tubos circulares - AISC E7 Sección E7.2(c)
    D/t = diámetro exterior / espesor de pared
    
    Para tubos circulares: Q se calcula directamente (no hay separación Qs/Qa)
    """
    limite = 0.11 * E / Fy
    
    if Dt_ratio <= limite:
        return 1.0
    else:
        # AISC E7-19: Fcr = 0.038E / (D/t)
        # Q efectivo se deriva de la reducción de Fcr
        return 0.038 * E / (Fy * Dt_ratio)


def _calcular_qa_hss_pared(bt_ratio: float, E: float, Fcr: float) -> float:
    """
    Qa para paredes de HSS rectangulares/cuadrados - AISC E7 Ec. E7-16, E7-17
    Similar al cálculo para almas, pero para paredes de HSS
    
    b/t = ancho de pared / espesor
    """
    raiz_E_f = np.sqrt(E / Fcr)
    
    if bt_ratio < 1.40 * raiz_E_f:
        return 1.0
    
    # Ancho efectivo
    factor = raiz_E_f / bt_ratio
    be_b = (1.0 - 0.34 * factor) * factor
    
    # Limitar
    be_b = min(max(be_b, 0.0), 1.0)
    
    return be_b


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
    # DOBLE T (incluyendo S-shapes)                                       #
    # ------------------------------------------------------------------ #
    if tipo in ['W', 'M', 'HP', 'S', 'IPE', 'IPN', 'IPB', 'IPBl', 'IPBv']:
        
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
                hw = props['basicas']['d'] - 2 * props['seccion']['tf']
                A_total = props['basicas']['Ag']
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
                hw = props['basicas']['d'] - 2 * props['seccion']['tf']
                A_total = props['basicas']['Ag']
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
    
    # ------------------------------------------------------------------ #
    # PERFIL T                                                            #
    # ------------------------------------------------------------------ #
    elif tipo in ['T', 'WT', 'MT', 'ST']:
        
        # Ala: elemento no rigidizado
        if 'ala' in clasificacion['elementos'] and \
           clasificacion['elementos']['ala']['clase'] == 'ESBELTA':
            bt_ala = props['seccion']['bf_2tf']
            Qs = _calcular_qs_ala_laminada(bt_ala, E, Fy)
            notas.append(f"Ala esbelta: bf/2tf = {bt_ala:.2f}, Qs = {Qs:.4f}")
        
        # Stem (alma): elemento no rigidizado para T
        if 'stem' in clasificacion['elementos'] and \
           clasificacion['elementos']['stem']['clase'] == 'ESBELTA':
            dt = props['seccion'].get('d_tw', props['seccion'].get('hw_tw', 0))
            if dt > 0:
                Qs_stem = _calcular_qs_stem_perfil_t(dt, E, Fy)
                Qs = min(Qs, Qs_stem)  # Tomar el menor
                notas.append(f"Stem esbelta: d/tw = {dt:.2f}, Qs_stem = {Qs_stem:.4f}")
    
    # ------------------------------------------------------------------ #
    # TUBO CIRCULAR                                                       #
    # ------------------------------------------------------------------ #
    elif tipo in ['TUBO CIRC.', 'PIPE']:
        
        if 'pared' in clasificacion['elementos'] and \
           clasificacion['elementos']['pared']['clase'] == 'ESBELTA':
            Dt = props['seccion'].get('D_t', 0)
            if Dt > 0:
                Q_tubo = _calcular_q_tubo_circular(Dt, E, Fy)
                # Para tubos circulares, Q se calcula directamente (no Qs × Qa)
                Qs = Q_tubo
                Qa = 1.0
                notas.append(f"Tubo circular esbelta: D/t = {Dt:.2f}, Q = {Q_tubo:.4f}")
    
    # ------------------------------------------------------------------ #
    # TUBO RECTANGULAR/CUADRADO                                           #
    # ------------------------------------------------------------------ #
    elif tipo in ['TUBO CUAD.', 'TUBO RECT.', 'HSS']:
        
        # Para HSS, todas las paredes son elementos rigidizados
        Qa_min = 1.0
        
        if 'flange' in clasificacion['elementos'] and \
           clasificacion['elementos']['flange']['clase'] == 'ESBELTA':
            if Fcr is not None:
                bt_flange = props['seccion'].get('b_t', 0)
                if bt_flange > 0:
                    Qa_flange = _calcular_qa_hss_pared(bt_flange, E, Fcr)
                    Qa_min = min(Qa_min, Qa_flange)
                    notas.append(f"Flange esbelta: b/t = {bt_flange:.2f}, Qa = {Qa_flange:.4f}")
        
        if 'web' in clasificacion['elementos'] and \
           clasificacion['elementos']['web']['clase'] == 'ESBELTA':
            if Fcr is not None:
                ht_web = props['seccion'].get('h_tw', 0)
                if ht_web > 0:
                    Qa_web = _calcular_qa_hss_pared(ht_web, E, Fcr)
                    Qa_min = min(Qa_min, Qa_web)
                    notas.append(f"Web esbelta: h/t = {ht_web:.2f}, Qa = {Qa_web:.4f}")
        
        if Fcr is None and Qa_min < 1.0:
            notas.append("ADVERTENCIA: Fcr no proporcionado, Qa = 1.0 (conservador)")
            Qa_min = 1.0
        
        Qa = Qa_min
    
    else:
        raise ValueError(
            f"Tipo '{tipo}' no soportado en calcular_Q. "
            f"Válidos: W, M, HP, S, IPE, IPN, IPB, IPBl, IPBv, C, MC, UPN, L, "
            f"T, WT, MT, ST, TUBO CIRC., PIPE, TUBO CUAD., TUBO RECT., HSS."
        )
    
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
    # DOBLE T (incluyendo S-shapes)                                       #
    # ------------------------------------------------------------------ #
    if tipo in ['W', 'M', 'HP', 'S', 'IPE', 'IPN', 'IPB', 'IPBl', 'IPBv']:

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

    # ------------------------------------------------------------------ #
    # PERFIL T                                                            #
    # ------------------------------------------------------------------ #
    elif tipo in ['T', 'WT', 'MT', 'ST']:

        lp, lr = _limites_ala_perfil_t(E, Fy)
        elementos['ala'] = _clasificar_elemento(
            'Ala (bf/2tf)', props['seccion']['bf_2tf'], lp, lr
        )
        
        lp, lr = _limites_alma_perfil_t(E, Fy)
        d_tw = props['seccion'].get('d_tw', props['seccion'].get('hw_tw', 0))
        elementos['stem'] = _clasificar_elemento(
            'Stem (d/tw)', d_tw, lp, lr
        )
        advertencias.append(
            "Perfil T: Stem no tiene λp en compresión (solo λr). "
            "Clasificación: COMPACTA o NO_COMPACTA no aplica para stem."
        )

    # ------------------------------------------------------------------ #
    # TUBO CIRCULAR                                                       #
    # ------------------------------------------------------------------ #
    elif tipo in ['TUBO CIRC.', 'PIPE']:

        lp, lr = _limites_tubo_circular(E, Fy)
        D_t = props['seccion'].get('D_t', 0)
        if D_t > 0:
            elementos['pared'] = _clasificar_elemento(
                'Pared (D/t)', D_t, lp, lr
            )
        else:
            advertencias.append("D/t no disponible para tubo circular")
        
        advertencias.append(
            "Tubo circular: No hay λp en compresión (solo λr = 0.11·E/Fy)."
        )

    # ------------------------------------------------------------------ #
    # TUBO RECTANGULAR/CUADRADO                                           #
    # ------------------------------------------------------------------ #
    elif tipo in ['TUBO CUAD.', 'TUBO RECT.', 'HSS']:

        lp, lr = _limites_tubo_rectangular_pared(E, Fy)
        
        # Flange (ancho)
        b_t = props['seccion'].get('b_t', 0)
        if b_t > 0:
            elementos['flange'] = _clasificar_elemento(
                'Flange (b/t)', b_t, lp, lr
            )
        
        # Web (altura) - solo para rectangulares
        if tipo in ['TUBO RECT.', 'HSS']:
            h_tw = props['seccion'].get('h_tw', 0)
            if h_tw > 0:
                elementos['web'] = _clasificar_elemento(
                    'Web (h/t)', h_tw, lp, lr
                )
        
        advertencias.append(
            "Tubo HSS: No hay λp en compresión (solo λr = 1.40·√(E/Fy))."
        )

    else:
        raise ValueError(
            f"Tipo '{tipo}' no soportado. "
            f"Válidos: W, M, HP, S, IPE, IPN, IPB, IPBl, IPBv, C, MC, UPN, L, "
            f"T, WT, MT, ST, TUBO CIRC., PIPE, TUBO CUAD., TUBO RECT., HSS."
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
