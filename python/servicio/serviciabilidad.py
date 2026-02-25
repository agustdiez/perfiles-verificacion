"""
serviciabilidad.py
==================
Cargas admisibles en servicio por deformación máxima.

Para un perfil, longitud L y deformación admisible δ_adm se calcula la
carga puntual P_adm y la carga distribuida q_adm que generan exactamente
δ_adm en el esquema estático seleccionado.

Esquemas implementados
----------------------
  CANTILEVER  : Voladizo — carga puntual en extremo libre / q distribuida
  SIMPLE      : Viga simplemente apoyada — P al centro / q uniforme
  EMPOTRADA   : Viga empotrada ambos extremos — P al centro / q uniforme

Fórmulas de flecha (elástica, primer orden)
-------------------------------------------
  Cantilever P     : δ = P·L³ / (3·E·I)       →  P = 3·E·I·δ / L³
  Cantilever q     : δ = q·L⁴ / (8·E·I)       →  q = 8·E·I·δ / L⁴
  Simple P centro  : δ = P·L³ / (48·E·I)      →  P = 48·E·I·δ / L³
  Simple q         : δ = 5·q·L⁴ / (384·E·I)   →  q = 384·E·I·δ / (5·L⁴)
  Empotrada P cen  : δ = P·L³ / (192·E·I)     →  P = 192·E·I·δ / L³
  Empotrada q      : δ = q·L⁴ / (384·E·I)     →  q = 384·E·I·δ / L⁴

Las cargas de eje fuerte y débil se informan de forma independiente
(sin superposición).

Unidades internas: mm, N, MPa  →  salida: kN (P), kN/m (q)

Referencias:
    Timoshenko & Gere — Mecánica de materiales
    CIRSOC 301:2005 / AISC 360-10 — Anexo de serviciabilidad
"""

import numpy as np
import sys
import os

_raiz_python = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _raiz_python not in sys.path:
    sys.path.insert(0, _raiz_python)

from core.utilidades_perfil import extraer_propiedades, verificar_propiedades


# ============================================================================
# CONSTANTES
# ============================================================================

E_ACERO = 200_000   # MPa = N/mm²


# ============================================================================
# CATÁLOGO DE ESQUEMAS ESTÁTICOS
# ============================================================================
# k_P: coeficiente tal que  P_adm = k_P * E * I * δ / L³  [N]
# k_q: coeficiente tal que  q_adm = k_q * E * I * δ / L⁴  [N/mm]

ESQUEMAS = {
    'CANTILEVER': {
        'descripcion'    : 'Voladizo — P en extremo libre / q uniforme',
        'descripcion_P'  : 'Carga puntual en extremo libre',
        'descripcion_q'  : 'Carga distribuida uniforme',
        'k_P'            : 3.0,
        'k_q'            : 8.0,
    },
    'SIMPLE': {
        'descripcion'    : 'Viga simplemente apoyada — P al centro / q uniforme',
        'descripcion_P'  : 'Carga puntual al centro',
        'descripcion_q'  : 'Carga distribuida uniforme',
        'k_P'            : 48.0,
        'k_q'            : 384.0 / 5.0,   # = 76.8
    },
    'EMPOTRADA': {
        'descripcion'    : 'Viga empotrada en ambos extremos — P al centro / q uniforme',
        'descripcion_P'  : 'Carga puntual al centro',
        'descripcion_q'  : 'Carga distribuida uniforme',
        'k_P'            : 192.0,
        'k_q'            : 384.0,
    },
}

# Fracciones de deformación admisible por defecto
FRACCIONES_CANTILEVER = [50, 100, 120, 150, 200]
FRACCIONES_OTRAS      = [100, 200, 300, 400, 500]


# ============================================================================
# CÁLCULO DE CARGA ADMISIBLE
# ============================================================================

def _p_adm_N(L: float, I: float, delta: float, k: float) -> float:
    """Carga puntual admisible [N]."""
    return k * E_ACERO * I * delta / L**3

def _q_adm_Nmm(L: float, I: float, delta: float, k: float) -> float:
    """Carga distribuida admisible [N/mm]."""
    return k * E_ACERO * I * delta / L**4


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def serviciabilidad(perfil_nombre: str,
                    L: float,
                    db_manager,
                    tipo_perfil: str = None,
                    esquema: str = 'SIMPLE',
                    fracciones: list = None) -> dict:
    """
    Calcular cargas admisibles en servicio para un perfil y longitud dados.

    Parámetros:
    -----------
    perfil_nombre : str             — Designación del perfil (ej: '18x97', 'W18X97', '100')
    L             : float           — Longitud del elemento [mm]
    db_manager    : GestorBaseDatos — Instancia con la BD activa
    tipo_perfil   : str, opcional   — Tipo para búsqueda exacta (ej: 'IPE', 'IPN')
                                      Requerido si perfil_nombre es ambiguo
    esquema       : str             — 'CANTILEVER' | 'SIMPLE' | 'EMPOTRADA'
    fracciones    : list[int]       — Denominadores δ_adm = L/n (ej: [100, 200, 300])
                                      Si None usa defaults por esquema

    Returns:
    --------
    dict con claves:
        'perfil'      : str
        'tipo'        : str
        'familia'     : str
        'base_datos'  : str
        'L_m'         : float  — longitud en metros
        'esquema'     : str
        'descripcion' : str
        'Ix_cm4'      : float  — inercia eje fuerte [cm⁴]
        'Iy_cm4'      : float  — inercia eje débil  [cm⁴]
        'tabla'       : list[dict] — una fila por fracción δ_adm:
            {
              'fraccion' : 'L/100'
              'delta_mm' : float   — δ admisible [mm]
              'Px_kN'    : float   — P admisible eje fuerte [kN]
              'qx_kNm'   : float   — q admisible eje fuerte [kN/m]
              'Py_kN'    : float   — P admisible eje débil  [kN]
              'qy_kNm'   : float   — q admisible eje débil  [kN/m]
            }
        'advertencias': list[str]
    """

    # ── Validar esquema ──────────────────────────────────────────────────
    esquema = esquema.upper().strip()
    if esquema not in ESQUEMAS:
        raise ValueError(
            f"Esquema '{esquema}' no reconocido. "
            f"Disponibles: {list(ESQUEMAS.keys())}"
        )
    if L <= 0:
        raise ValueError(f"L debe ser positivo. Recibido: {L}")

    cfg   = ESQUEMAS[esquema]
    fracs = fracciones if fracciones is not None else (
        FRACCIONES_CANTILEVER if esquema == 'CANTILEVER' else FRACCIONES_OTRAS
    )

    # ── Propiedades del perfil ───────────────────────────────────────────
    perfil    = db_manager.obtener_datos_perfil(perfil_nombre, tipo=tipo_perfil)
    bd_nombre = db_manager.nombre_base_activa()
    props     = extraer_propiedades(perfil, base_datos=bd_nombre)
    familia   = props['familia']
    tipo      = props['tipo']

    verif        = verificar_propiedades(props)
    advertencias = list(verif['advertencias'])

    # Inercias en mm⁴
    if familia == 'ANGULAR':
        Ix = float(props['flexion']['Ix'])
        Iy = Ix   # ángulo igual: Ix = Iy
        advertencias.append(
            'Angular (ángulo igual): Ix = Iy — tabla idéntica en ambos ejes.'
        )
    else:
        Ix = float(props['flexion']['Ix'])
        Iy = float(props['flexion']['Iy'])

    if Ix <= 0 or Iy <= 0:
        raise ValueError(
            f"Inercias no válidas para '{perfil_nombre}': Ix={Ix}, Iy={Iy}"
        )

    k_P = cfg['k_P']
    k_q = cfg['k_q']

    # ── Tabla de doble entrada ───────────────────────────────────────────
    tabla = []
    for denom in fracs:
        if denom <= 0:
            continue
        delta = float(L) / denom   # mm

        Px = _p_adm_N(L, Ix, delta, k_P) / 1000       # N → kN
        qx = _q_adm_Nmm(L, Ix, delta, k_q) * 1000     # N/mm → kN/m
        Py = _p_adm_N(L, Iy, delta, k_P) / 1000
        qy = _q_adm_Nmm(L, Iy, delta, k_q) * 1000

        tabla.append({
            'fraccion': f'L/{denom}',
            'delta_mm': round(float(delta), 2),
            'Px_kN'   : round(float(Px), 2),
            'qx_kNm'  : round(float(qx), 3),
            'Py_kN'   : round(float(Py), 2),
            'qy_kNm'  : round(float(qy), 3),
        })

    return {
        'perfil'      : perfil_nombre,
        'tipo'        : tipo,
        'familia'     : familia,
        'base_datos'  : bd_nombre,
        'L_mm'        : float(L),
        'L_m'         : round(float(L) / 1000, 3),
        'esquema'     : esquema,
        'descripcion' : cfg['descripcion'],
        'desc_P'      : cfg['descripcion_P'],
        'desc_q'      : cfg['descripcion_q'],
        'Ix_mm4'      : float(Ix),
        'Iy_mm4'      : float(Iy),
        'Ix_cm4'      : round(float(Ix) / 1e4, 1),
        'Iy_cm4'      : round(float(Iy) / 1e4, 1),
        'tabla'       : tabla,
        'advertencias': advertencias,
    }


# ============================================================================
# REPORTE EN CONSOLA
# ============================================================================

def imprimir_tabla(r: dict):
    """Imprimir la tabla de serviciabilidad en consola."""
    if 'error' in r:
        print(f"\n  ❌ {r.get('perfil','?')}: {r['error']}")
        return

    print()
    print("=" * 82)
    print("  SERVICIABILIDAD — Cargas admisibles por deformación")
    print("=" * 82)
    print(f"  Perfil  : {r['perfil']}  ({r['tipo']} — {r['familia']})")
    print(f"  BD      : {r['base_datos']}")
    print(f"  L       : {r['L_m']} m  ({r['L_mm']:.0f} mm)")
    print(f"  Esquema : {r['esquema']} — {r['descripcion']}")
    print(f"  P → {r['desc_P']}")
    print(f"  q → {r['desc_q']}")
    print(f"  Ix = {r['Ix_cm4']} cm⁴   Iy = {r['Iy_cm4']} cm⁴")
    print("-" * 82)
    hdr = (f"  {'δ adm':>7}  {'δ [mm]':>7}  "
           f"{'Px [kN]':>9}  {'qx[kN/m]':>10}  "
           f"{'Py [kN]':>9}  {'qy[kN/m]':>10}")
    print(hdr)
    print("  " + "-" * 78)
    for f in r['tabla']:
        print(f"  {f['fraccion']:>7}  {f['delta_mm']:>7.1f}  "
              f"{f['Px_kN']:>9.1f}  {f['qx_kNm']:>10.2f}  "
              f"{f['Py_kN']:>9.1f}  {f['qy_kNm']:>10.2f}")
    print("=" * 82)
    for adv in r.get('advertencias', []):
        print(f"  ⚠️   {adv}")
    if r.get('advertencias'):
        print()


# ============================================================================
# BLOQUE DE PRUEBA
# ============================================================================

if __name__ == '__main__':

    from core.gestor_base_datos import GestorBaseDatos

    db = GestorBaseDatos()
    db.cambiar_base('CIRSOC')
    L = 5000   # mm

    # ── 1. Los tres esquemas con W18x97 ──────────────────────────────────
    for esq, fracs in [
        ('CANTILEVER', [50, 100, 120, 150, 200]),
        ('SIMPLE',     [100, 200, 300, 400, 500]),
        ('EMPOTRADA',  [100, 200, 300, 400, 500]),
    ]:
        r = serviciabilidad('18x97', L=L, db_manager=db,
                            esquema=esq, fracciones=fracs)
        imprimir_tabla(r)

    # ── 2. Canal C15x50 ──────────────────────────────────────────────────
    r_c = serviciabilidad('C15x50', L=3000, db_manager=db,
                          esquema='CANTILEVER',
                          fracciones=[50, 100, 120, 150, 200])
    imprimir_tabla(r_c)

    # ── 3. Verificación cruzada AISC ─────────────────────────────────────
    db.cambiar_base('AISC')
    r_aisc = serviciabilidad('W18X97', L=L, db_manager=db,
                             esquema='SIMPLE',
                             fracciones=[300, 500])
    imprimir_tabla(r_aisc)

    # ── 4. Verificación manual Simple L/300 ──────────────────────────────
    # δ = 5qL⁴/(384EI) → q = 384·E·I·δ/(5·L⁴)
    db.cambiar_base('CIRSOC')
    r_v = serviciabilidad('18x97', L=L, db_manager=db,
                          esquema='SIMPLE', fracciones=[300])
    Ix   = r_v['Ix_mm4']
    delt = L / 300
    q_manual = (384 / 5) * E_ACERO * Ix * delt / L**4 * 1000   # kN/m
    q_tabla  = r_v['tabla'][0]['qx_kNm']
    print(f"\n  Verificación manual Simple L/300:")
    print(f"    Ix = {Ix/1e6:.3f} ×10⁶ mm⁴   δ = {delt:.2f} mm")
    print(f"    q manual = {q_manual:.3f} kN/m")
    print(f"    q tabla  = {q_tabla:.3f} kN/m")
    print(f"    Δ        = {abs(q_manual-q_tabla):.6f} kN/m  ({'OK ✅' if abs(q_manual-q_tabla)<0.01 else 'ERROR ❌'})")

    # ── 5. Angular ───────────────────────────────────────────────────────
    db.cambiar_base('CIRSOC')
    r_ang = serviciabilidad('L 4x4x1/2', L=2000, db_manager=db,
                            esquema='SIMPLE', fracciones=[200, 300])
    imprimir_tabla(r_ang)
