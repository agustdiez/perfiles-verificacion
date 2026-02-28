"""
interaccion.py
==============
Verificación de flexocompresión según CIRSOC 301 / AISC 360-10 — Capítulo H.

Flexión biaxial:
    Si Nu/Pd ≥ 0.2 → H1-1a:  Nu/Pd  +  8/9·(Mux/Mdx + Muy/Mdy)  ≤ 1.0
    Si Nu/Pd < 0.2 → H1-1b:  Nu/(2·Pd)  +  (Mux/Mdx + Muy/Mdy)  ≤ 1.0

Nu [kN], Mux, Muy [kN·m].
"""

import numpy as np, sys, os

_raiz_python = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _raiz_python not in sys.path:
    sys.path.insert(0, _raiz_python)

from resistencia.compresion import compresion
from resistencia.flexion    import flexion


def interaccion(perfil_nombre: str,
                Fy: float,
                Lx: float,
                Ly: float,
                Lb: float,
                db_manager,
                Nu: float,
                Mux: float = 0.0,
                Muy: float = 0.0,
                tipo_perfil: str = None,
                Lz: float = None,
                Kx: float = 1.0,
                Ky: float = 1.0,
                Kz: float = 1.0,
                Cb: float = 1.0,
                mostrar_calculo: bool = True) -> dict:
    """
    Parámetros:
    -----------
    perfil_nombre   : str   — designación del perfil (ej: 'W310x97', '100')
    Fy              : float — tensión de fluencia [MPa]
    Lx, Ly, Lz      : float — longitudes de pandeo [mm]
    Lb              : float — longitud sin arriostrar lateral [mm]
    db_manager      : GestorBaseDatos
    Nu              : float — carga axial de compresión de diseño [kN]
    Mux             : float — momento flector eje fuerte [kN·m]
    Muy             : float — momento flector eje débil [kN·m]
    tipo_perfil     : str, opcional — tipo para búsqueda exacta (ej: 'IPE', 'IPN')
                                      Requerido si perfil_nombre es ambiguo
    Lz, Kx, Ky, Kz  : float — parámetros de pandeo
    Cb              : float — factor momento (default: 1.0)
    mostrar_calculo : bool

    Returns dict:
        'ratio' [adim], 'cumple' [bool], 'ecuacion', 'Pd' [kN], 
        'Mdx', 'Mdy' [kN·m], 'Nu_Pd', 'Mux_Mdx', 'Muy_Mdy' [adim]
    """
    if Lz is None:
        Lz = max(Lx, Ly)

    advertencias = []

    res_comp = compresion(
        perfil_nombre=perfil_nombre, tipo_perfil=tipo_perfil, Fy=Fy,
        Lx=Lx, Ly=Ly, db_manager=db_manager, Lz=Lz,
        Kx=Kx, Ky=Ky, Kz=Kz, mostrar_calculo=False,
    )
    res_flex = flexion(
        perfil_nombre=perfil_nombre, tipo_perfil=tipo_perfil, Fy=Fy,
        Lb=Lb, db_manager=db_manager, Cb=Cb, 
        calcular_ambos_ejes=True, mostrar_calculo=False,
    )

    Pd  = res_comp['Pd']
    Mdx = res_flex['Mdx']
    Mdy = res_flex['Mdy']
    
    advertencias.extend(res_comp.get('advertencias', []))
    advertencias.extend(res_flex.get('advertencias', []))

    if Pd <= 0:
        advertencias.append('Pd ≤ 0: interacción no calculada.')
        return {
            'perfil': perfil_nombre, 
            'ratio': float('nan'),
            'cumple': False, 
            'ecuacion': '—',
            'Pd': Pd, 'Mdx': Mdx, 'Mdy': Mdy,
            'Nu_Pd': float('nan'),
            'Mux_Mdx': float('nan'), 
            'Muy_Mdy': float('nan'),
            'advertencias': advertencias
        }

    # Ratios individuales
    Nu_Pd   = Nu / Pd if Pd > 0 else 0.0
    Mux_Mdx = Mux / Mdx if Mdx > 0 and not np.isnan(Mdx) else 0.0
    Muy_Mdy = Muy / Mdy if Mdy > 0 and not np.isnan(Mdy) else 0.0
    
    # Suma de ratios de flexión
    M_ratio_sum = Mux_Mdx + Muy_Mdy

    # Ecuación H1-1 (biaxial)
    if Nu_Pd >= 0.2:
        ratio    = Nu_Pd + 8/9 * M_ratio_sum
        ecuacion = 'H1-1a'
    else:
        ratio    = Nu_Pd / 2 + M_ratio_sum
        ecuacion = 'H1-1b'

    resultado = {
        'perfil'       : perfil_nombre,
        'tipo'         : res_comp.get('tipo', ''),
        'familia'      : res_comp.get('familia', ''),
        'base_datos'   : db_manager.nombre_base_activa(),
        'Fy': Fy, 'Lx': Lx, 'Ly': Ly, 'Lb': Lb, 
        'Nu': Nu, 'Mux': Mux, 'Muy': Muy,
        'Pd'           : round(Pd, 1),
        'Mdx'          : round(Mdx, 1) if not np.isnan(Mdx) else float('nan'),
        'Mdy'          : round(Mdy, 1) if not np.isnan(Mdy) else float('nan'),
        'Nu_Pd'        : round(Nu_Pd, 4),
        'Mux_Mdx'      : round(Mux_Mdx, 4),
        'Muy_Mdy'      : round(Muy_Mdy, 4),
        'ratio'        : round(ratio, 4),
        'cumple'       : bool(ratio <= 1.0),
        'ecuacion'     : ecuacion,
        'modo_comp'    : res_comp.get('modo_pandeo', ''),
        'modo_flex_x'  : res_flex.get('modo_x', ''),
        'modo_flex_y'  : res_flex.get('modo_y', ''),
        'clase_seccion': res_comp.get('clase_seccion', ''),
        'esbeltez_max' : res_comp.get('esbeltez_max', 0.0),
        'Lp'           : res_flex.get('Lp', float('nan')),
        'Lr'           : res_flex.get('Lr', float('nan')),
        'advertencias' : advertencias,
    }

    if mostrar_calculo:
        _imprimir_reporte(resultado)
    return resultado


def _imprimir_reporte(r: dict):
    print()
    print("=" * 70)
    print("  FLEXOCOMPRESIÓN BIAXIAL — H1-1  (CIRSOC 301 / AISC 360-10)")
    print("=" * 70)
    print(f"  Perfil : {r['perfil']}   ({r['tipo']} — {r['familia']})")
    print(f"  Fy={r['Fy']}MPa  Nu={r['Nu']}kN  Mux={r['Mux']}kN·m  Muy={r['Muy']}kN·m")
    print(f"  Lx={r['Lx']:.0f}mm  Ly={r['Ly']:.0f}mm  Lb={r['Lb']:.0f}mm")
    print("-" * 70)
    print(f"  RESISTENCIAS:")
    print(f"    Pd  = {r['Pd']:.1f} kN")
    print(f"    Mdx = {r['Mdx']:.1f} kN·m" if not np.isnan(r['Mdx']) else "    Mdx = N/A")
    print(f"    Mdy = {r['Mdy']:.1f} kN·m" if not np.isnan(r['Mdy']) else "    Mdy = N/A")
    print()
    print(f"  RATIOS:")
    print(f"    Nu/Pd    = {r['Nu_Pd']:.4f}")
    print(f"    Mux/Mdx  = {r['Mux_Mdx']:.4f}")
    print(f"    Muy/Mdy  = {r['Muy_Mdy']:.4f}")
    print()
    print(f"  {r['ecuacion']}: ratio = {r['ratio']:.4f}  →  "
          f"{'✅ CUMPLE' if r['cumple'] else '❌ NO CUMPLE'}")
    print("=" * 70)
    for adv in r.get('advertencias', []):
        print(f"  ⚠️   {adv}")


if __name__ == '__main__':
    from core.gestor_base_datos import GestorBaseDatos
    db = GestorBaseDatos()
    db.cambiar_base('CIRSOC')

    print("\n=== TEST 1: Flexión biaxial ===")
    interaccion('18x97', Fy=250, Lx=5000, Ly=5000, Lb=5000,
                db_manager=db, Nu=1000, Mux=200, Muy=50)
    
    print("\n=== TEST 2: Solo compresión ===")
    interaccion('18x97', Fy=250, Lx=5000, Ly=5000, Lb=5000,
                db_manager=db, Nu=2000, Mux=0, Muy=0)
    
    print("\n=== TEST 3: Solo flexión en X ===")
    interaccion('18x97', Fy=250, Lx=5000, Ly=5000, Lb=5000,
                db_manager=db, Nu=0, Mux=500, Muy=0)
