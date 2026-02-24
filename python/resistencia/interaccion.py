"""
interaccion.py
==============
Verificación de flexocompresión según CIRSOC 301 / AISC 360-10 — Capítulo H.

    Si Nu/Pd ≥ 0.2 → H1-1a:  Nu/Pd  +  8/9·(Mu/Md)  ≤ 1.0
    Si Nu/Pd < 0.2 → H1-1b:  Nu/(2·Pd)  +  Mu/Md    ≤ 1.0

Flexión uniaxial en eje fuerte. Nu [kN], Mu [kN·m].
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
                Mu: float,
                Lz: float = None,
                Kx: float = 1.0,
                Ky: float = 1.0,
                Kz: float = 1.0,
                Cb: float = 1.0,
                mostrar_calculo: bool = True) -> dict:
    """
    Parámetros:
    -----------
    Lx, Ly, Lz  : longitudes de pandeo [mm]
    Lb          : longitud sin arriostrar lateral [mm]
    Nu          : carga axial de compresión de diseño [kN]
    Mu          : momento flector de diseño [kN·m]

    Returns dict:
        'ratio' [adim], 'cumple' [bool], 'ecuacion', 'Pd' [kN], 'Md' [kN·m]
    """
    if Lz is None:
        Lz = max(Lx, Ly)

    advertencias = []

    res_comp = compresion(
        perfil_nombre=perfil_nombre, Fy=Fy,
        Lx=Lx, Ly=Ly, db_manager=db_manager, Lz=Lz,
        Kx=Kx, Ky=Ky, Kz=Kz, mostrar_calculo=False,
    )
    res_flex = flexion(
        perfil_nombre=perfil_nombre, Fy=Fy,
        Lb=Lb, db_manager=db_manager, Cb=Cb, mostrar_calculo=False,
    )

    Pd = res_comp['Pd']
    Md = res_flex['Md']
    advertencias.extend(res_comp.get('advertencias', []))
    advertencias.extend(res_flex.get('advertencias', []))

    if Pd <= 0:
        advertencias.append('Pd ≤ 0: interacción no calculada.')
        return {'perfil': perfil_nombre, 'ratio': float('nan'),
                'cumple': False, 'ecuacion': '—',
                'Pd': Pd, 'Md': Md, 'Nu_Pd': float('nan'),
                'Mu_Md': float('nan'), 'advertencias': advertencias}

    Nu_Pd = Nu / Pd if Pd > 0 else 0.0
    Mu_Md = Mu / Md if Md > 0 else 0.0

    if Nu_Pd >= 0.2:
        ratio    = Nu_Pd + 8/9 * Mu_Md
        ecuacion = 'H1-1a'
    else:
        ratio    = Nu_Pd / 2 + Mu_Md
        ecuacion = 'H1-1b'

    resultado = {
        'perfil'       : perfil_nombre,
        'tipo'         : res_comp.get('tipo', ''),
        'familia'      : res_comp.get('familia', ''),
        'base_datos'   : db_manager.nombre_base_activa(),
        'Fy': Fy, 'Lx': Lx, 'Ly': Ly, 'Lb': Lb, 'Nu': Nu, 'Mu': Mu,
        'Pd'           : round(Pd, 1),
        'Md'           : round(Md, 1),
        'Nu_Pd'        : round(Nu_Pd, 4),
        'Mu_Md'        : round(Mu_Md, 4),
        'ratio'        : round(ratio, 4),
        'cumple'       : bool(ratio <= 1.0),
        'ecuacion'     : ecuacion,
        'modo_comp'    : res_comp.get('modo_pandeo', ''),
        'modo_flex'    : res_flex.get('modo', ''),
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
    print("=" * 62)
    print("  FLEXOCOMPRESIÓN — H1-1  (CIRSOC 301 / AISC 360-10)")
    print("=" * 62)
    print(f"  Perfil : {r['perfil']}   ({r['tipo']} — {r['familia']})")
    print(f"  Fy={r['Fy']}MPa  Nu={r['Nu']}kN  Mu={r['Mu']}kN·m")
    print(f"  Lx={r['Lx']:.0f}mm  Ly={r['Ly']:.0f}mm  Lb={r['Lb']:.0f}mm")
    print("-" * 62)
    print(f"  Pd = {r['Pd']:.1f} kN    Md = {r['Md']:.1f} kN·m")
    print(f"  Nu/Pd = {r['Nu_Pd']:.3f}   Mu/Md = {r['Mu_Md']:.3f}")
    print(f"  {r['ecuacion']}: ratio = {r['ratio']:.4f}  →  "
          f"{'✅ CUMPLE' if r['cumple'] else '❌ NO CUMPLE'}")
    print("=" * 62)
    for adv in r.get('advertencias', []):
        print(f"  ⚠️   {adv}")


if __name__ == '__main__':
    from core.gestor_base_datos import GestorBaseDatos
    db = GestorBaseDatos()
    db.cambiar_base('CIRSOC')

    interaccion('18x97', Fy=250, Lx=5000, Ly=5000, Lb=5000,
                db_manager=db, Nu=1000, Mu=300)
    interaccion('18x97', Fy=250, Lx=5000, Ly=5000, Lb=5000,
                db_manager=db, Nu=2000, Mu=0)
    interaccion('18x97', Fy=250, Lx=5000, Ly=5000, Lb=5000,
                db_manager=db, Nu=0, Mu=500)
