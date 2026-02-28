"""
flexion.py
==========
Resistencia a flexión según CIRSOC 301 / AISC 360-10.

Límites de resistencia implementados:
    Doble T (W, HP, M, S, IPB, IPBl, IPBv, IPE, IPN):
        ✅ Eje fuerte: F2 — LTB + F3 — FLB
        ✅ Eje débil: F6 — Solo FLB (sin LTB)
    Canal (C, MC, UPN):
        ✅ Eje fuerte: F2 simplificado (conservador)
        ✅ Eje débil: F6 — Solo FLB
    Angular (L):
        ✅ F10 simplificado: Mn = 1.5·My
    Perfil T (WT, MT, ST, T):
        ✅ F9 — Stem en compresión (conservador)
    Tubo Circular (PIPE, TUBO CIRC.):
        ✅ F8 — Sección circular compacta
    Tubo Rectangular (HSS, TUBO CUAD., TUBO RECT.):
        ✅ F7 — FLB y WLB (ambos ejes)

Unidades internas: mm / N / MPa  →  salida: kN·m
φb = 0.90 (LRFD)
"""

import numpy as np
import sys
import os

_raiz_python = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _raiz_python not in sys.path:
    sys.path.insert(0, _raiz_python)

from core.utilidades_perfil import extraer_propiedades


# ============================================================================
# CONSTANTES
# ============================================================================

E_ACERO = 200_000
G_ACERO =  77_200
PHI_B   =    0.90


# ============================================================================
# HELPERS — AISC F2 (EJE FUERTE - LTB)
# ============================================================================

def _rts(Iy, Cw, Sx):
    """rts² = √(Iy·Cw) / Sx  →  rts [mm]"""
    return np.sqrt(np.sqrt(Iy * Cw) / Sx)


def _Lp(ry, E, Fy):
    """Longitud límite plástica. F2-5."""
    return 1.76 * ry * np.sqrt(E / Fy)


def _Lr(rts, E, Fy, J, Sx, ho):
    """Longitud límite LTB inelástico. F2-6."""
    u = J / (Sx * ho)
    return 1.95 * rts * (E / (0.7 * Fy)) * np.sqrt(
        u + np.sqrt(u**2 + 6.76 * (0.7 * Fy / E)**2)
    )


def _Mn_LTB(Lb, Lp, Lr, Mp, Fy, Sx, Cb, E, rts, J, ho):
    """Mn por LTB. F2-1 a F2-4."""
    if Lb <= Lp:
        return Mp, 'Fluencia'
    elif Lb <= Lr:
        Mn = Cb * (Mp - (Mp - 0.7 * Fy * Sx) * (Lb - Lp) / (Lr - Lp))
        return min(Mn, Mp), 'LTB inelástico'
    else:
        slend = Lb / rts
        Fcr = Cb * np.pi**2 * E / slend**2 * np.sqrt(
            1 + 0.078 * J / (Sx * ho) * slend**2
        )
        return min(Fcr * Sx, Mp), 'LTB elástico'


def _Mn_FLB(Mp, Fy, Sx, lam_f, E):
    """Mn por FLB. F3. Retorna (Mn, modo, lam_pf, lam_rf)."""
    lam_pf = 0.38 * np.sqrt(E / Fy)
    lam_rf = 1.0  * np.sqrt(E / Fy)
    if lam_f <= lam_pf:
        return Mp, 'Ala compacta', lam_pf, lam_rf
    elif lam_f <= lam_rf:
        Mn = Mp - (Mp - 0.7 * Fy * Sx) * (lam_f - lam_pf) / (lam_rf - lam_pf)
        return Mn, 'FLB inelástico', lam_pf, lam_rf
    else:
        Kc  = min(max(4.0 / np.sqrt(lam_f), 0.35), 0.76)
        Fcr = 0.9 * E * Kc / lam_f**2
        return min(Fcr * Sx, Mp), 'FLB elástico', lam_pf, lam_rf


# ============================================================================
# HELPERS — EJE DÉBIL (AISC F6)
# ============================================================================

def _Mn_eje_debil(Fy, Sy, Zy, bf_2tf, E):
    """
    Flexión eje débil (y-y) para doble T y canales - AISC F6.
    No hay LTB para flexión eje débil, solo FLB.
    """
    My = Fy * Sy
    Mp = Fy * Zy if Zy > 0 else 1.12 * My
    
    lam_pf = 0.38 * np.sqrt(E / Fy)
    lam_rf = 1.0  * np.sqrt(E / Fy)
    
    if bf_2tf <= lam_pf:
        return Mp, 'Compacta', lam_pf, lam_rf
    elif bf_2tf <= lam_rf:
        Mn = Mp - (Mp - My) * (bf_2tf - lam_pf) / (lam_rf - lam_pf)
        return Mn, 'No compacta', lam_pf, lam_rf
    else:
        Fcr = 0.69 * E / bf_2tf**2
        return min(Fcr * Sy, Mp), 'Esbelta', lam_pf, lam_rf


# ============================================================================
# HELPERS — NUEVAS FAMILIAS
# ============================================================================

def _Mn_perfil_T(Fy, Sx, Zx, d_tw, E):
    """Flexión para perfiles T - AISC F9 (stem en compresión)."""
    My = Fy * Sx
    Mp = Fy * Zx if Zx > 0 else 1.5 * My
    
    lam_p = 0.84 * np.sqrt(E / Fy)
    lam_r = 1.03 * np.sqrt(E / Fy)
    
    if d_tw <= lam_p:
        return Mp, 'Stem compacto', lam_p, lam_r
    elif d_tw <= lam_r:
        Mn = Mp - (Mp - My) * (d_tw - lam_p) / (lam_r - lam_p)
        return Mn, 'Stem no compacto', lam_p, lam_r
    else:
        Fcr = 0.69 * E / d_tw**2
        return min(Fcr * Sx, Mp), 'Stem esbelta', lam_p, lam_r


def _Mn_tubo_circular(Fy, Z, D_t, E):
    """Flexión para tubos circulares - AISC F8."""
    Mp = Fy * Z
    lam_p = 0.07 * E / Fy
    
    if D_t <= lam_p:
        return Mp, 'Compacto', lam_p, lam_p
    else:
        factor = 0.021 * E / (D_t * Fy)
        return min(factor, 1.0) * Mp, 'No compacto', lam_p, lam_p


def _Mn_HSS_rectangular(Fy, Sx, Zx, b_t, h_t, E, eje='fuerte'):
    """Flexión para HSS rectangulares - AISC F7."""
    My = Fy * Sx
    Mp = Fy * Zx if Zx > 0 else 1.12 * My
    
    # Límites para flanges (perpendicular al eje de flexión)
    lam_pf = 1.12 * np.sqrt(E / Fy)
    lam_rf = 1.40 * np.sqrt(E / Fy)
    
    # Límites para webs (paralelo al eje de flexión)
    lam_pw = 2.42 * np.sqrt(E / Fy)
    lam_rw = 5.70 * np.sqrt(E / Fy)
    
    # Para eje fuerte: b es flange, h es web
    # Para eje débil: h es flange, b es web
    if eje == 'fuerte':
        lam_flange, lam_pf_use, lam_rf_use = b_t, lam_pf, lam_rf
        lam_web, lam_pw_use, lam_rw_use = h_t, lam_pw, lam_rw
    else:
        lam_flange, lam_pf_use, lam_rf_use = h_t, lam_pf, lam_rf
        lam_web, lam_pw_use, lam_rw_use = b_t, lam_pw, lam_rw
    
    # Verificar flange
    if lam_flange <= lam_pf_use:
        Mn_flange, modo_flange = Mp, 'Flange compacto'
    elif lam_flange <= lam_rf_use:
        Mn_flange = Mp - (Mp - My) * (lam_flange - lam_pf_use) / (lam_rf_use - lam_pf_use)
        modo_flange = 'Flange no compacto'
    else:
        Fcr = 0.69 * E / lam_flange**2
        Mn_flange = min(Fcr * Sx, Mp)
        modo_flange = 'Flange esbelta'
    
    # Verificar web
    if lam_web <= lam_pw_use:
        Mn_web, modo_web = Mp, 'Web compacto'
    elif lam_web <= lam_rw_use:
        Mn_web = Mp - (Mp - My) * (lam_web - lam_pw_use) / (lam_rw_use - lam_pw_use)
        modo_web = 'Web no compacto'
    else:
        Fcr = 0.69 * E / lam_web**2
        Mn_web = min(Fcr * Sx, Mp)
        modo_web = 'Web esbelta'
    
    # Gobierna el menor
    if Mn_flange <= Mn_web:
        return Mn_flange, modo_flange, lam_pf_use, lam_rf_use
    else:
        return Mn_web, modo_web, lam_pw_use, lam_rw_use


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def flexion(perfil_nombre: str,
            Fy: float,
            Lb: float,
            db_manager,
            tipo_perfil: str = None,
            eje: str = 'fuerte',
            Cb: float = 1.0,
            calcular_ambos_ejes: bool = False,
            mostrar_calculo: bool = True) -> dict:
    """
    Resistencia a flexión según CIRSOC 301 / AISC 360-10.

    Parámetros:
    -----------
    perfil_nombre   : str   — designación del perfil (ej: 'W310x97', '100')
    Fy              : float — tensión de fluencia [MPa]
    Lb              : float — longitud sin arriostrar lateral [mm]
    db_manager      : GestorBaseDatos
    tipo_perfil     : str, opcional — tipo para búsqueda exacta (ej: 'IPE', 'IPN')
    eje             : str   — 'fuerte' (x-x) o 'debil' (y-y), default 'fuerte'
    Cb              : float — modificador de diagrama de momento (default 1.0)
    calcular_ambos_ejes : bool — si True, calcula ambos ejes (cuando aplicable)
    mostrar_calculo : bool

    Returns dict:
        'Mdx'   [kN·m]  resistencia de diseño eje fuerte
        'Mnx'   [kN·m]  resistencia nominal eje fuerte
        'Mpx'   [kN·m]  momento plástico eje fuerte
        'Mdy'   [kN·m]  resistencia de diseño eje débil (o None)
        'Mny'   [kN·m]  resistencia nominal eje débil (o None)
        'Mpy'   [kN·m]  momento plástico eje débil (o None)
        'Lp'    [mm]    longitud límite plástica
        'Lr'    [mm]    longitud límite LTB inelástico
        'modo_x' [str]  modo eje fuerte
        'modo_y' [str]  modo eje débil (o None)
        'Md'    [kN·m]  = Mdx o Mdy según 'eje' (compatibilidad)
        'Mn'    [kN·m]  = Mnx o Mny según 'eje'
        'advertencias' [list]
    """

    # ── 1. Datos ─────────────────────────────────────────────────────────────
    perfil    = db_manager.obtener_datos_perfil(perfil_nombre, tipo=tipo_perfil)
    bd_nombre = db_manager.nombre_base_activa()
    tipo      = str(perfil['Tipo']).strip()

    props   = extraer_propiedades(perfil, base_datos=bd_nombre)
    familia = props['familia']

    advertencias = []
    resultados = {
        'perfil'    : perfil_nombre,
        'tipo'      : tipo,
        'familia'   : familia,
        'base_datos': bd_nombre,
        'Fy'        : Fy,
        'phi_b'     : PHI_B,
        'Lb'        : Lb,
        'Cb'        : Cb,
        'Mdx'       : float('nan'),
        'Mdy'       : float('nan'),
        'Mnx'       : float('nan'),
        'Mny'       : float('nan'),
        'Mpx'       : float('nan'),
        'Mpy'       : float('nan'),
        'modo_x'    : '',
        'modo_y'    : '',
    }

    # ── 2. Por familia ────────────────────────────────────────────────────────

    if familia in ('DOBLE_T', 'CANAL'):

        Sx     = float(props['flexion']['Sx'])
        Iy     = float(props['flexion']['Iy'])
        ry     = float(props['flexion']['ry'])
        J      = float(props['torsion']['J'])
        Cw     = float(props['torsion']['Cw'])
        d      = float(props['basicas']['d'])
        tf     = float(props['seccion']['tf'])
        bf_2tf = float(props['seccion']['bf_2tf'])

        # Zx: si falta, aproximar
        Zx_raw = props['flexion'].get('Zx', None)
        try:
            Zx = float(Zx_raw) if Zx_raw is not None else 0.0
            if np.isnan(Zx) or Zx == 0.0:
                raise ValueError
        except (TypeError, ValueError):
            Zx = 1.12 * Sx
            advertencias.append('Zx no disponible: se usó Zx ≈ 1.12·Sx')

        Mp  = Fy * Zx
        My  = Fy * Sx
        ho  = d - tf

        rts_v = _rts(Iy, Cw, Sx)
        Lp_v  = _Lp(ry, E_ACERO, Fy)
        Lr_v  = _Lr(rts_v, E_ACERO, Fy, J, Sx, ho)

        # EJE FUERTE
        Mn_ltb, modo_ltb = _Mn_LTB(
            Lb, Lp_v, Lr_v, Mp, Fy, Sx, Cb, E_ACERO, rts_v, J, ho
        )

        if bf_2tf > 0:
            Mn_flb, modo_flb, lam_pf, lam_rf = _Mn_FLB(Mp, Fy, Sx, bf_2tf, E_ACERO)
        else:
            Mn_flb, modo_flb = Mp, 'Ala compacta (bf/2tf=0)'
            lam_pf = 0.38 * np.sqrt(E_ACERO / Fy)
            lam_rf = 1.0  * np.sqrt(E_ACERO / Fy)
            advertencias.append('bf/2tf=0: FLB no verificado (asume ala compacta)')

        Mn_x   = min(Mn_ltb, Mn_flb)
        modo_x = modo_ltb if Mn_ltb <= Mn_flb else modo_flb

        if familia == 'CANAL':
            advertencias.append(
                'Canal: LTB calculado con F2 (simetría simple — conservador).'
            )

        resultados.update({
            'Mnx'     : round(Mn_x    / 1e6, 2),
            'Mdx'     : round(PHI_B * Mn_x / 1e6, 2),
            'Mpx'     : round(Mp      / 1e6, 2),
            'Myx'     : round(My      / 1e6, 2),
            'Lp'      : round(Lp_v,   0),
            'Lr'      : round(Lr_v,   0),
            'rts'     : round(rts_v,  2),
            'ho'      : round(ho,     2),
            'Mn_ltb'  : round(Mn_ltb  / 1e6, 2),
            'Mn_flb'  : round(Mn_flb  / 1e6, 2),
            'modo_ltb': modo_ltb,
            'modo_flb': modo_flb,
            'modo_x'  : modo_x,
            'lam_f'   : round(bf_2tf, 2),
            'lam_pf'  : round(lam_pf, 2),
            'lam_rf'  : round(lam_rf, 2),
        })

        # EJE DÉBIL (si se solicita)
        if calcular_ambos_ejes:
            Sy = float(props['flexion']['Sy'])
            Zy_raw = props['flexion'].get('Zy', None)
            try:
                Zy = float(Zy_raw) if Zy_raw is not None else 0.0
                if np.isnan(Zy) or Zy == 0.0:
                    Zy = 1.12 * Sy
                    advertencias.append('Zy no disponible: Zy ≈ 1.12·Sy')
            except (TypeError, ValueError):
                Zy = 1.12 * Sy
                advertencias.append('Zy no disponible: Zy ≈ 1.12·Sy')

            Mn_y, modo_y, lam_py, lam_ry = _Mn_eje_debil(Fy, Sy, Zy, bf_2tf, E_ACERO)

            resultados.update({
                'Mny'    : round(Mn_y    / 1e6, 2),
                'Mdy'    : round(PHI_B * Mn_y / 1e6, 2),
                'Mpy'    : round(Fy * Zy / 1e6, 2) if Zy > 0 else round(1.12 * Fy * Sy / 1e6, 2),
                'Myy'    : round(Fy * Sy / 1e6, 2),
                'modo_y' : modo_y,
                'lam_py' : round(lam_py, 2),
                'lam_ry' : round(lam_ry, 2),
            })

    elif familia == 'ANGULAR':

        Sx = float(props['flexion']['Sx'])
        My = Fy * Sx
        Mn = 1.5 * My          # AISC F10-1 (ángulo igual compacto)
        advertencias.append(
            'Angular: Mn = 1.5·My (F10 simplificado). LTB no calculado.'
        )
        resultados.update({
            'Mnx'  : round(Mn / 1e6, 2),
            'Mdx'  : round(PHI_B * Mn / 1e6, 2),
            'Mpx'  : round(Mn / 1e6, 2),
            'Myx'  : round(My / 1e6, 2),
            'Lp'   : float('nan'),
            'Lr'   : float('nan'),
            'modo_x': 'F10 simplificado (1.5·My)',
            'Mdy'  : float('nan'),
            'modo_y': '',
        })

    elif familia == 'PERFIL_T':
        
        Sx = float(props['flexion']['Sx'])
        Zx_raw = props['flexion'].get('Zx', None)
        try:
            Zx = float(Zx_raw) if Zx_raw is not None else 0.0
            if np.isnan(Zx) or Zx == 0.0:
                Zx = 1.5 * Sx
                advertencias.append('Zx no disponible: Zx ≈ 1.5·Sx')
        except (TypeError, ValueError):
            Zx = 1.5 * Sx
            advertencias.append('Zx no disponible: Zx ≈ 1.5·Sx')
        
        d_tw = float(props['seccion'].get('d_tw', props['seccion'].get('hw_tw', 0)))
        
        Mn_x, modo_x, lam_p, lam_r = _Mn_perfil_T(Fy, Sx, Zx, d_tw, E_ACERO)
        
        resultados.update({
            'Mnx'   : round(Mn_x / 1e6, 2),
            'Mdx'   : round(PHI_B * Mn_x / 1e6, 2),
            'Mpx'   : round(Fy * Zx / 1e6, 2),
            'Myx'   : round(Fy * Sx / 1e6, 2),
            'Lp'    : float('nan'),
            'Lr'    : float('nan'),
            'modo_x': modo_x,
            'lam_p' : round(lam_p, 2),
            'lam_r' : round(lam_r, 2),
            'Mdy'   : float('nan'),
            'modo_y': '',
        })
        advertencias.append('Perfil T: solo eje fuerte significativo.')

    elif familia == 'TUBO_CIRCULAR':
        
        Zx = float(props['flexion']['Zx'])
        D_t = float(props['seccion'].get('D_t', 0))
        
        Mn_x, modo_x, lam_p, lam_r = _Mn_tubo_circular(Fy, Zx, D_t, E_ACERO)
        
        resultados.update({
            'Mnx'   : round(Mn_x / 1e6, 2),
            'Mdx'   : round(PHI_B * Mn_x / 1e6, 2),
            'Mpx'   : round(Fy * Zx / 1e6, 2),
            'Lp'    : float('nan'),
            'Lr'    : float('nan'),
            'modo_x': modo_x,
            'lam_p' : round(lam_p, 2),
            # Simétrico
            'Mny'   : round(Mn_x / 1e6, 2),
            'Mdy'   : round(PHI_B * Mn_x / 1e6, 2),
            'Mpy'   : round(Fy * Zx / 1e6, 2),
            'modo_y': modo_x,
        })
        advertencias.append('Tubo circular: simétrico (Mdx = Mdy).')

    elif familia in ('TUBO_RECTANGULAR', 'TUBO_CUADRADO'):
        
        Sx = float(props['flexion']['Sx'])
        Zx_raw = props['flexion'].get('Zx', None)
        try:
            Zx = float(Zx_raw) if Zx_raw is not None else 0.0
            if np.isnan(Zx) or Zx == 0.0:
                Zx = 1.12 * Sx
                advertencias.append('Zx no disponible: Zx ≈ 1.12·Sx')
        except (TypeError, ValueError):
            Zx = 1.12 * Sx
            advertencias.append('Zx no disponible: Zx ≈ 1.12·Sx')
        
        b_t = float(props['seccion'].get('b_t', 0))
        h_t = float(props['seccion'].get('h_tw', 0))
        
        # Eje fuerte
        Mn_x, modo_x, lam_px, lam_rx = _Mn_HSS_rectangular(Fy, Sx, Zx, b_t, h_t, E_ACERO, eje='fuerte')
        
        resultados.update({
            'Mnx'   : round(Mn_x / 1e6, 2),
            'Mdx'   : round(PHI_B * Mn_x / 1e6, 2),
            'Mpx'   : round(Fy * Zx / 1e6, 2),
            'Myx'   : round(Fy * Sx / 1e6, 2),
            'Lp'    : float('nan'),
            'Lr'    : float('nan'),
            'modo_x': modo_x,
            'lam_px': round(lam_px, 2),
            'lam_rx': round(lam_rx, 2),
        })
        
        # Eje débil (si se solicita)
        if calcular_ambos_ejes and familia == 'TUBO_RECTANGULAR':
            Sy = float(props['flexion']['Sy'])
            Zy_raw = props['flexion'].get('Zy', None)
            try:
                Zy = float(Zy_raw) if Zy_raw is not None else 0.0
                if np.isnan(Zy) or Zy == 0.0:
                    Zy = 1.12 * Sy
            except (TypeError, ValueError):
                Zy = 1.12 * Sy
            
            Mn_y, modo_y, lam_py, lam_ry = _Mn_HSS_rectangular(Fy, Sy, Zy, b_t, h_t, E_ACERO, eje='debil')
            
            resultados.update({
                'Mny'   : round(Mn_y / 1e6, 2),
                'Mdy'   : round(PHI_B * Mn_y / 1e6, 2),
                'Mpy'   : round(Fy * Zy / 1e6, 2),
                'Myy'   : round(Fy * Sy / 1e6, 2),
                'modo_y': modo_y,
                'lam_py': round(lam_py, 2),
                'lam_ry': round(lam_ry, 2),
            })
        elif familia == 'TUBO_CUADRADO':
            # Cuadrado: ambos ejes iguales
            resultados.update({
                'Mny'   : resultados['Mnx'],
                'Mdy'   : resultados['Mdx'],
                'Mpy'   : resultados['Mpx'],
                'modo_y': modo_x,
            })

    else:
        raise ValueError(f"Familia '{familia}' no implementada.")

    # ── 3. Compatibilidad hacia atrás ────────────────────────────────────────
    if eje == 'fuerte':
        resultados['Md'] = resultados['Mdx']
        resultados['Mn'] = resultados['Mnx']
        resultados['Mp'] = resultados['Mpx']
        resultados['modo'] = resultados['modo_x']
    else:
        resultados['Md'] = resultados['Mdy'] if not np.isnan(resultados['Mdy']) else resultados['Mdx']
        resultados['Mn'] = resultados['Mny'] if not np.isnan(resultados['Mny']) else resultados['Mnx']
        resultados['Mp'] = resultados['Mpy'] if not np.isnan(resultados['Mpy']) else resultados['Mpx']
        resultados['modo'] = resultados['modo_y'] if resultados['modo_y'] != '' else resultados['modo_x']

    resultados['advertencias'] = advertencias

    if mostrar_calculo:
        _imprimir_reporte(resultados)

    return resultados


# ============================================================================
# REPORTE
# ============================================================================

def _imprimir_reporte(r: dict):
    Lp = r.get('Lp', float('nan'))
    try:
        Lp_f = float(Lp)
        tiene_Lp = not np.isnan(Lp_f)
    except (TypeError, ValueError):
        tiene_Lp = False

    print()
    print("=" * 62)
    print("  FLEXIÓN — CIRSOC 301 / AISC 360-10")
    print("=" * 62)
    print(f"  Perfil     : {r['perfil']}   ({r['tipo']} — {r['familia']})")
    print(f"  Base datos : {r['base_datos']}")
    print(f"  Fy = {r['Fy']} MPa    Cb = {r['Cb']}")
    print(f"  Lb = {r['Lb']:.0f} mm = {r['Lb']/1000:.2f} m")
    print("-" * 62)

    if tiene_Lp:
        print(f"  Lp = {r['Lp']:.0f} mm  ({r['Lp']/1000:.2f} m)")
        print(f"  Lr = {r['Lr']:.0f} mm  ({r['Lr']/1000:.2f} m)")
        print(f"  rts = {r.get('rts', '—')} mm    ho = {r.get('ho', '—')} mm")
        if 'modo_ltb' in r:
            print(f"  Modo LTB : {r['modo_ltb']}")
            print(f"  Modo FLB : {r['modo_flb']}")
        print("-" * 62)

    # Eje fuerte
    print(f"  EJE FUERTE (x-x):")
    print(f"    Mpx  = {r['Mpx']:.1f} kN·m")
    if 'Myx' in r:
        print(f"    Myx  = {r['Myx']:.1f} kN·m")
    if 'Mn_ltb' in r:
        print(f"    Mn_LTB = {r['Mn_ltb']:.1f} kN·m")
        print(f"    Mn_FLB = {r['Mn_flb']:.1f} kN·m")
    print(f"    Mnx  = {r['Mnx']:.1f} kN·m  ({r['modo_x']})")
    print(f"    Mdx  = φb·Mnx = {r['phi_b']} × {r['Mnx']:.1f} = {r['Mdx']:.1f} kN·m")
    
    # Eje débil (si existe y no es NaN)
    if not np.isnan(r['Mdy']):
        print(f"  EJE DÉBIL (y-y):")
        print(f"    Mpy  = {r['Mpy']:.1f} kN·m")
        if 'Myy' in r and not np.isnan(r.get('Myy', float('nan'))):
            print(f"    Myy  = {r['Myy']:.1f} kN·m")
        print(f"    Mny  = {r['Mny']:.1f} kN·m  ({r['modo_y']})")
        print(f"    Mdy  = φb·Mny = {r['phi_b']} × {r['Mny']:.1f} = {r['Mdy']:.1f} kN·m")
    
    print("=" * 62)
    for adv in r.get('advertencias', []):
        print(f"  ⚠️   {adv}")
    if r.get('advertencias'):
        print()


# ============================================================================
# PRUEBA
# ============================================================================

if __name__ == '__main__':
    from core.gestor_base_datos import GestorBaseDatos

    db = GestorBaseDatos()

    print("\n=== TEST CIRSOC - Doble T ===")
    db.cambiar_base('CIRSOC')
    r1 = flexion('100', Fy=250, Lb=3000, db_manager=db, tipo_perfil='IPE', 
                 calcular_ambos_ejes=True)
    
    print("\n=== TEST AISC - W-shape ===")
    db.cambiar_base('AISC')
    r2 = flexion('W18X97', Fy=250, Lb=5000, db_manager=db, 
                 calcular_ambos_ejes=True)
