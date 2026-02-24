"""
flexion.py
==========
Resistencia a flexión (eje fuerte) según CIRSOC 301 / AISC 360-10.

Límites de resistencia implementados:
    Doble T (W, HP, M, S, IPB, IPBl, IPBv, IPE, IPN):
        ✅ F2 — LTB: fluencia / inelástico / elástico
        ✅ F3 — FLB: compacta / no-compacta / esbelta
    Canal (C, MC, UPN):
        ✅ F2 simplificado (mismas ecuaciones — conservador para simetría simple)
    Angular (L):
        ✅ F10 simplificado: Mn = 1.5·My

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
# HELPERS — AISC F2
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
# FUNCIÓN PRINCIPAL
# ============================================================================

def flexion(perfil_nombre: str,
            Fy: float,
            Lb: float,
            db_manager,
            Cb: float = 1.0,
            mostrar_calculo: bool = True) -> dict:
    """
    Resistencia a flexión en eje fuerte según CIRSOC 301 / AISC 360-10.

    Parámetros:
    -----------
    perfil_nombre   : str   — designación del perfil
    Fy              : float — tensión de fluencia [MPa]
    Lb              : float — longitud sin arriostrar lateral [mm]
    db_manager      : GestorBaseDatos
    Cb              : float — modificador de diagrama de momento (default 1.0)
    mostrar_calculo : bool

    Returns dict:
        'Md'   [kN·m]  resistencia de diseño
        'Mn'   [kN·m]  resistencia nominal
        'Mp'   [kN·m]  momento plástico
        'Lp'   [mm]    longitud límite plástica
        'Lr'   [mm]    longitud límite LTB inelástico
        'modo' [str]   modo que gobierna
        'advertencias' [list]
    """

    # ── 1. Datos ─────────────────────────────────────────────────────────────
    perfil    = db_manager.obtener_datos_perfil(perfil_nombre)
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

        Mn   = min(Mn_ltb, Mn_flb)
        modo = modo_ltb if Mn_ltb <= Mn_flb else modo_flb

        if familia == 'CANAL':
            advertencias.append(
                'Canal: LTB calculado con F2 (simetría simple — conservador).'
            )

        resultados.update({
            'Mn'      : round(Mn      / 1e6, 2),
            'Md'      : round(PHI_B * Mn / 1e6, 2),
            'Mp'      : round(Mp      / 1e6, 2),
            'My'      : round(My      / 1e6, 2),
            'Lp'      : round(Lp_v,   0),
            'Lr'      : round(Lr_v,   0),
            'rts'     : round(rts_v,  2),
            'ho'      : round(ho,     2),
            'Mn_ltb'  : round(Mn_ltb  / 1e6, 2),
            'Mn_flb'  : round(Mn_flb  / 1e6, 2),
            'modo_ltb': modo_ltb,
            'modo_flb': modo_flb,
            'modo'    : modo,
            'lam_f'   : round(bf_2tf, 2),
            'lam_pf'  : round(lam_pf, 2),
            'lam_rf'  : round(lam_rf, 2),
        })

    elif familia == 'ANGULAR':

        Sx = float(props['flexion']['Sx'])
        My = Fy * Sx
        Mn = 1.5 * My          # AISC F10-1 (ángulo igual compacto)
        advertencias.append(
            'Angular: Mn = 1.5·My (F10 simplificado). LTB no calculado.'
        )
        resultados.update({
            'Mn'  : round(Mn / 1e6, 2),
            'Md'  : round(PHI_B * Mn / 1e6, 2),
            'Mp'  : round(Mn / 1e6, 2),
            'My'  : round(My / 1e6, 2),
            'Lp'  : float('nan'),
            'Lr'  : float('nan'),
            'modo': 'F10 simplificado (1.5·My)',
        })

    else:
        raise ValueError(f"Familia '{familia}' no implementada.")

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
        print(f"  Modo LTB : {r.get('modo_ltb', '—')}")
        print(f"  Modo FLB : {r.get('modo_flb', '—')}")
        print("-" * 62)

    print(f"  Mp  = {r['Mp']:.1f} kN·m")
    print(f"  My  = {r['My']:.1f} kN·m")
    if 'Mn_ltb' in r:
        print(f"  Mn_LTB = {r['Mn_ltb']:.1f} kN·m")
        print(f"  Mn_FLB = {r['Mn_flb']:.1f} kN·m")
    print(f"  Mn  = {r['Mn']:.1f} kN·m  ({r['modo']})")
    print(f"  Md  = φb·Mn = {r['phi_b']} × {r['Mn']:.1f} = {r['Md']:.1f} kN·m")
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

    print("\n=== TEST CIRSOC ===")
    db.cambiar_base('CIRSOC')
    r1 = flexion('18x97',  Fy=250, Lb=1000, db_manager=db)
    r2 = flexion('18x97',  Fy=250, Lb=5000, db_manager=db)
    r3 = flexion('C15x50', Fy=250, Lb=3000, db_manager=db)

    print("\n=== TEST AISC ===")
    db.cambiar_base('AISC')
    r4 = flexion('W18X97', Fy=250, Lb=5000, db_manager=db)
    r5 = flexion('C15X50', Fy=250, Lb=3000, db_manager=db)
