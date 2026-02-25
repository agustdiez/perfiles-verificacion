"""
utilidades_perfil.py
====================
Extracción y conversión de propiedades geométricas de perfiles
desde las bases de datos CIRSOC y AISC.

Las funciones de resistencia y clasificación SIEMPRE reciben las propiedades
ya convertidas a unidades SI (mm, mm², mm⁴, mm⁶). La conversión ocurre
una sola vez aquí; el resto del código nunca necesita pensar en unidades.

Unidades de salida garantizadas:
    Longitudes          : mm
    Áreas               : mm²
    Inercias (Ix, Iy…)  : mm⁴
    Módulos (Sx, Zx…)   : mm³
    Radios de giro      : mm
    J                   : mm⁴
    Cw                  : mm⁶
    ro                  : mm
    H                   : adimensional

Conversiones aplicadas por base de datos (verificadas cruzando rx=√(Ix/A)):
                  CIRSOC                  AISC
  Área (mm²)    Ag [cm²]  × 100         A  [mm²]     × 1
  Inercias(mm⁴) Ix [cm⁴]  × 1e4        Ix [mm⁴/1e6] × 1e6
  Radios (mm)   rx [cm]   × 10          rx [mm]      × 1
  J (mm⁴)       J  [cm⁴]  × 1e4        J  [mm⁴/1e3] × 1e3
  Cw (mm⁶)      Cw [cm⁶]  × 1e6        Cw [mm⁶/1e9] × 1e9
  x, eo (mm)    x  [cm]   × 10          x  [mm]      × 1
  d,bf,tf,tw    mm         × 1           mm           × 1
  hw (mm)       columna hw × 1           h/tw × tw    (calculado)
  ro, H         calculados               tabulados (C, MC, L)
"""

import numpy as np
import pandas as pd


# ============================================================================
# FAMILIAS
# ============================================================================

FAMILIAS = {
    'DOBLE_T'     : ['W', 'M', 'HP', 'S', 'IPE', 'IPN', 'IPB', 'IPBl', 'IPBv'],
    'CANAL'       : ['C', 'MC', 'UPN'],
    'ANGULAR'     : ['L'],
    'PERFIL_T'    : ['T', 'WT', 'MT', 'ST'],
    'TUBO_CIRC'   : ['TUBO CIRC.', 'PIPE'],
    'TUBO_CUAD'   : ['TUBO CUAD.', 'HSS'],  # HSS puede ser cuadrado o rectangular
    'TUBO_RECT'   : ['TUBO RECT.', 'HSS'],  # Se determina por bf: si bf > 0 → rect, sino cuad
}


# ============================================================================
# UTILIDADES GENERALES
# ============================================================================

def a_flotante(valor, default: float = 0.0) -> float:
    """Conversión segura a float. Devuelve `default` ante NaN o strings."""
    try:
        v = float(valor)
        return v if not np.isnan(v) else default
    except (ValueError, TypeError):
        return default


def determinar_familia(tipo: str, perfil: pd.Series = None) -> str:
    """
    Retorna 'DOBLE_T' | 'CANAL' | 'ANGULAR' | 'PERFIL_T' | 
           'TUBO_CIRC' | 'TUBO_CUAD' | 'TUBO_RECT' | 'DESCONOCIDA'.
    
    Para HSS (AISC), determina si es cuadrado o rectangular según dimensiones.
    """
    # HSS necesita lógica especial
    if tipo == 'HSS' and perfil is not None:
        # Intentar determinar si es cuadrado o rectangular
        # HSS tiene columna 'B' para ancho en AISC
        try:
            b_val = perfil.get('B', 0)
            # Si no hay B o B=0, asumir que es de la otra familia (no importa cuál)
            # Si hay B, verificar si es cuadrado (d ≈ B) o rectangular (d != B)
            if b_val and b_val > 0:
                d_val = perfil.get('d', 0)
                # Tolerancia del 5% para considerar cuadrado
                if abs(d_val - b_val) / max(d_val, b_val, 1) < 0.05:
                    return 'TUBO_CUAD'
                else:
                    return 'TUBO_RECT'
        except:
            pass
        # Default: probar con TUBO_CUAD primero
        return 'TUBO_CUAD'
    
    # Otros tipos: búsqueda normal
    for familia, tipos in FAMILIAS.items():
        if tipo in tipos:
            return familia
    
    return 'DESCONOCIDA'


# ============================================================================
# MAPAS DE COLUMNAS Y FACTORES DE CONVERSIÓN
# ============================================================================
#
# Formato de cada entrada: (nombre_columna_bd, factor_multiplicador)
# None indica que la columna no existe → se calcula o se devuelve 0.0
#

_MAPA_BASE = {
    'CIRSOC': {
        'area'  : ('Ag',    100.0),
        'peso'  : ('Peso',    1.0),
        'd'     : ('d',       1.0),
        'bf'    : ('bf',      1.0),
        'tf'    : ('tf',      1.0),
        'tw'    : ('tw',      1.0),
        'hw'    : ('hw',      1.0),
        'Ix'    : ('Ix',     1e4),
        'Sx'    : ('Sx',     1e3),
        'rx'    : ('rx',     10.0),
        'Zx'    : ('Zx',     1e3),
        'Iy'    : ('Iy',     1e4),
        'Sy'    : ('Sy',     1e3),
        'ry'    : ('ry',     10.0),
        'Zy'    : ('Zy',     1e3),
        'J'     : ('J',      1e4),
        'Cw'    : ('Cw',     1e6),
        'x'     : ('x',      10.0),
        'eo'    : ('eo',     10.0),
        'bf_2tf': ('bf/2tf',  1.0),
        'hw_tw' : ('hw/tw',   1.0),
    },
    'AISC': {
        'area'  : ('A',       1.0),
        'peso'  : ('W',       1.0),
        'd'     : ('d',       1.0),
        'bf'    : ('bf',      1.0),
        'tf'    : ('tf',      1.0),
        'tw'    : ('tw',      1.0),
        'hw'    : None,              # calcular: hw_tw × tw
        'Ix'    : ('Ix',     1e6),
        'Sx'    : ('Sx',     1e3),
        'rx'    : ('rx',      1.0),
        'Zx'    : ('Zx',     1e3),
        'Iy'    : ('Iy',     1e6),
        'Sy'    : ('Sy',     1e3),
        'ry'    : ('ry',      1.0),
        'Zy'    : ('Zy',     1e3),
        'J'     : ('J',      1e3),
        'Cw'    : ('Cw',     1e9),
        'x'     : ('x',       1.0),
        'eo'    : ('eo',      1.0),
        'bf_2tf': ('bf/2tf',  1.0),
        'hw_tw' : ('h/tw',    1.0),
    },
}

_MAPA_ANGULAR = {
    'CIRSOC': {
        'b'     : ('b',      1.0),
        't'     : ('t',      1.0),
        'Ix_ang': ('Ix-Iy', 1e4),   # ángulo igual: Ix = Iy
        'Sx_ang': ('Sx-Sy', 1e3),
        'rx_ang': ('rx-ry', 10.0),
        'Iv'    : ('Iv',    1e4),
        'Sv'    : ('Sv',    1e3),
        'iv'    : ('iv',    10.0),
        'Iz'    : ('Iz',    1e4),
        'iz'    : ('iz',    10.0),
        'b_t'   : ('b/t',   1.0),
        'ex_ey' : ('ex-ey', 10.0),
    },
    'AISC': {
        'b'     : ('b',      1.0),
        't'     : ('t',      1.0),
        'Ix_ang': ('Ix',    1e6),
        'Sx_ang': ('Sx',    1e3),
        'rx_ang': ('rx',     1.0),
        'Iv'    : ('Iw',    1e6),   # Iw AISC = inercia eje mayor principal (w)
        'Sv'    : None,              # no tabulado → 0.0
        'iv'    : ('rz',     1.0),  # rz AISC = radio eje menor principal = iv CIRSOC
        'Iz'    : ('Iz',    1e6),
        'iz'    : ('rz',     1.0),
        'b_t'   : ('b/t',   1.0),
        'ex_ey' : ('x',      1.0),  # x = y para ángulo igual
    },
}

_MAPA_PERFIL_T = {
    'CIRSOC': {
        'd'     : ('d',      1.0),
        'bf'    : ('bf',     1.0),
        'tf'    : ('tf',     1.0),
        'area'  : ('Ag',   100.0),
        'peso'  : ('Peso',   1.0),
        'Ix'    : ('Ix',    1e4),
        'Sx'    : ('Sx',    1e3),
        'rx'    : ('rx',    10.0),
        'Zx'    : ('Zx',    1e3),
        'Iy'    : ('Iy',    1e4),
        'Sy'    : ('Sy',    1e3),
        'ry'    : ('ry',    10.0),
        'Zy'    : ('Zy',    1e3),
        'J'     : ('J',     1e4),
        'Cw'    : ('Cw',    1e6),
        'bf_2tf': ('bf/2tf', 1.0),
        'd_tw'  : ('d/tw',   1.0),
    },
    'AISC': {
        'd'     : ('d',      1.0),
        'bf'    : ('bf',     1.0),
        'tf'    : ('tf',     1.0),
        'tw'    : ('tw',     1.0),
        'area'  : ('A',      1.0),
        'peso'  : ('W',      1.0),
        'Ix'    : ('Ix',    1e6),
        'Sx'    : ('Sx',    1e3),
        'rx'    : ('rx',     1.0),
        'Zx'    : ('Zx',    1e3),
        'Iy'    : ('Iy',    1e6),
        'Sy'    : ('Sy',    1e3),
        'ry'    : ('ry',     1.0),
        'Zy'    : ('Zy',    1e3),
        'J'     : ('J',     1e3),
        'Cw'    : ('Cw',    1e9),
        'bf_2tf': ('bf/2tf', 1.0),
        'd_tw'  : ('d/tw',   1.0),
    },
}

_MAPA_TUBO = {
    'CIRSOC': {
        'd'     : ('d',      1.0),  # diámetro o altura
        'bf'    : ('bf',     1.0),  # ancho (solo rect.)
        't'     : ('tf',     1.0),  # espesor
        'area'  : ('Ag',   100.0),
        'peso'  : ('Peso',   1.0),
        'Ix'    : ('Ix',    1e4),
        'Sx'    : ('Sx',    1e3),
        'rx'    : ('rx',    10.0),
        'Zx'    : ('Zx',    1e3),
        'Iy'    : ('Iy',    1e4),
        'Sy'    : ('Sy',    1e3),
        'ry'    : ('ry',    10.0),
        'Zy'    : ('Zy',    1e3),
        'J'     : ('J',     1e4),
        'Cw'    : ('Cw',    1e6),
    },
    'AISC': {
        # Intentar múltiples columnas para d, bf, t (diferentes entre PIPE y HSS)
        'd'     : [('Ht', 1.0), ('OD', 1.0)],  # HSS: Ht, PIPE: OD
        'bf'    : [('B', 1.0)],                 # HSS: B
        't'     : [('tdes', 1.0), ('t', 1.0)], # HSS: tdes, PIPE: t
        'area'  : ('A',      1.0),
        'peso'  : ('W',      1.0),
        'Ix'    : ('Ix',    1e6),
        'Sx'    : ('Sx',    1e3),
        'rx'    : ('rx',     1.0),
        'Zx'    : ('Zx',    1e3),
        'Iy'    : ('Iy',    1e6),
        'Sy'    : ('Sy',    1e3),
        'ry'    : ('ry',     1.0),
        'Zy'    : ('Zy',    1e3),
        'J'     : ('J',     1e3),
        'Cw'    : None,              # No disponible en AISC tubos
    },
}


def _leer(perfil: pd.Series, clave: str, bd: str,
          mapa: dict = None, default: float = 0.0) -> float:
    """
    Leer y convertir una propiedad del perfil usando el mapa indicado.

    Devuelve `default` si la entrada del mapa es None o la columna no existe.
    
    Soporta múltiples columnas alternativas: si entrada es una lista,
    intenta cada columna en orden hasta encontrar una con valor válido.
    """
    if mapa is None:
        mapa = _MAPA_BASE
    entrada = mapa[bd].get(clave)
    if entrada is None:
        return default
    
    # Soportar lista de alternativas: [(col1, factor1), (col2, factor2), ...]
    if isinstance(entrada, list):
        for col, factor in entrada:
            valor = a_flotante(perfil.get(col, None), None)
            if valor is not None:  # Encontró valor válido
                return valor * factor
        return default  # Ninguna alternativa tuvo valor
    
    # Entrada simple: (col, factor)
    col, factor = entrada
    return a_flotante(perfil.get(col, default), default) * factor


# ============================================================================
# EXTRACCIÓN DE PROPIEDADES
# ============================================================================

def extraer_propiedades(perfil: pd.Series, base_datos: str = 'CIRSOC') -> dict:
    """
    Extraer propiedades geométricas de un perfil y convertirlas a mm/mm²/mm⁴/mm⁶.

    Parámetros:
    -----------
    perfil     : pd.Series — fila de la base de datos
    base_datos : str       — 'CIRSOC' | 'AISC'

    Returns:
    --------
    dict con claves:
        'tipo', 'familia', 'basicas', 'flexion', 'torsion',
        'seccion', 'centro_corte', 'disponibles'

    Todas las magnitudes en mm / mm² / mm⁴ / mm⁶.
    """
    bd   = base_datos.upper()
    tipo = str(perfil['Tipo']).strip()

    if bd not in ('CIRSOC', 'AISC'):
        raise ValueError(f"Base '{bd}' no reconocida. Use 'CIRSOC' o 'AISC'.")

    props = {
        'tipo'        : tipo,
        'familia'     : determinar_familia(tipo, perfil),
        'basicas'     : {},
        'flexion'     : {},
        'torsion'     : {},
        'seccion'     : {},
        'centro_corte': {},
        'disponibles' : [],
    }

    # Determinar familia una vez
    familia = props['familia']
    
    # Atajos para no repetir bd en cada llamada
    R = lambda clave, default=0.0: _leer(perfil, clave, bd, default=default)
    L = lambda clave, default=0.0: _leer(perfil, clave, bd,
                                          mapa=_MAPA_ANGULAR, default=default)

    # ------------------------------------------------------------------ #
    # DOBLE T: W, M, HP, S, IPE, IPN, IPB, IPBl, IPBv                    #
    # ------------------------------------------------------------------ #
    if familia == 'DOBLE_T':

        props['basicas'] = {
            'd'   : R('d'),
            'bf'  : R('bf'),
            'Ag'  : R('area'),
            'Peso': R('peso'),
        }

        props['flexion'] = {
            'Ix': R('Ix'), 'Sx': R('Sx'), 'rx': R('rx'), 'Zx': R('Zx'),
            'Iy': R('Iy'), 'Sy': R('Sy'), 'ry': R('ry'), 'Zy': R('Zy'),
        }

        props['torsion'] = {'J': R('J'), 'Cw': R('Cw')}

        hw = R('hw_tw') * R('tw') if bd == 'AISC' else R('hw')

        props['seccion'] = {
            'tf'    : R('tf'),
            'tw'    : R('tw'),
            'hw'    : hw,
            'bf_2tf': R('bf_2tf'),
            'hw_tw' : R('hw_tw'),
        }

        Ag = props['basicas']['Ag']
        Ix = props['flexion']['Ix']
        Iy = props['flexion']['Iy']
        props['centro_corte'] = {
            'xo': 0.0,
            'yo': 0.0,
            'ro': np.sqrt((Ix + Iy) / Ag) if Ag > 0 else 0.0,
            'H' : 1.0,
        }

        props['disponibles'] = [
            'd', 'bf', 'tf', 'tw', 'hw', 'Ag',
            'Ix', 'Iy', 'Sx', 'Sy', 'rx', 'ry', 'Zx', 'Zy', 'J', 'Cw',
        ]

    # ------------------------------------------------------------------ #
    # CANAL: C, MC, UPN                                                   #
    # ------------------------------------------------------------------ #
    elif familia == 'CANAL':

        props['basicas'] = {
            'd'   : R('d'),
            'bf'  : R('bf'),
            'Ag'  : R('area'),
            'Peso': R('peso'),
        }

        props['flexion'] = {
            'Ix': R('Ix'), 'Sx': R('Sx'), 'rx': R('rx'), 'Zx': R('Zx'),
            'Iy': R('Iy'), 'Sy': R('Sy'), 'ry': R('ry'), 'Zy': R('Zy'),
        }

        props['torsion'] = {'J': R('J'), 'Cw': R('Cw')}

        tf  = R('tf')
        tw  = R('tw')
        hw  = R('hw_tw') * tw if bd == 'AISC' else R('hw')

        bf_2tf = R('bf_2tf')
        # AISC no precalcula bf/2tf para canales → calcular
        if bf_2tf == 0.0 and R('bf') > 0 and tf > 0:
            bf_2tf = R('bf') / (2 * tf)

        props['seccion'] = {
            'tf'    : tf,
            'tw'    : tw,
            'hw'    : hw,
            'bf_2tf': bf_2tf,
            'hw_tw' : R('hw_tw'),
        }

        x_mm  = R('x')
        eo_mm = R('eo')
        Ag    = props['basicas']['Ag']
        Ix    = props['flexion']['Ix']
        Iy    = props['flexion']['Iy']

        if bd == 'AISC':
            ro_tab = a_flotante(perfil.get('ro', 0))
            H_tab  = a_flotante(perfil.get('H',  0))
            if ro_tab > 0 and H_tab > 0:
                ro = ro_tab
                H  = H_tab
                xo = np.sqrt((1 - H) * ro**2)
            else:
                # Fallback: calcular (raro, solo si faltan en BD)
                xo = abs(x_mm - eo_mm)
                ro = np.sqrt(xo**2 + (Ix + Iy) / Ag) if Ag > 0 else 0.0
                H  = 1 - xo**2 / ro**2 if ro > 0 else 1.0
        else:
            # CIRSOC: xo = distancia del centroide al centro de corte
            xo = abs(x_mm - eo_mm)
            ro = np.sqrt(xo**2 + (Ix + Iy) / Ag) if Ag > 0 else 0.0
            H  = 1 - xo**2 / ro**2 if ro > 0 else 1.0

        props['centro_corte'] = {
            'xo': xo,
            'yo': 0.0,
            'ro': ro,
            'H' : H,
            'x' : x_mm,
            'eo': eo_mm,
        }

        props['disponibles'] = [
            'd', 'bf', 'tf', 'tw', 'hw', 'Ag',
            'Ix', 'Iy', 'Sx', 'Sy', 'rx', 'ry', 'Zx', 'Zy', 'J', 'Cw',
            'x', 'eo',
        ]

    # ------------------------------------------------------------------ #
    # ANGULAR: L                                                          #
    # ------------------------------------------------------------------ #
    elif familia == 'ANGULAR':

        b  = L('b')
        t  = L('t')
        Ag = R('area')

        Ix = L('Ix_ang')
        Sx = L('Sx_ang')
        rx = L('rx_ang')
        Iv = L('Iv')
        Sv = L('Sv')
        iv = L('iv')
        Iz = L('Iz')
        iz = L('iz')

        props['basicas'] = {
            'b'   : b,
            't'   : t,
            'Ag'  : Ag,
            'Peso': R('peso'),
        }

        props['flexion'] = {
            'Ix': Ix, 'Sx': Sx, 'rx': rx,
            'Iy': Ix, 'Sy': Sx, 'ry': rx,   # iguales en ángulo igual
            'Iv': Iv, 'Sv': Sv, 'iv': iv,
            'Iz': Iz, 'iz': iz,
        }

        props['torsion'] = {'J': R('J'), 'Cw': R('Cw')}

        props['seccion'] = {
            'b'  : b,
            't'  : t,
            'b_t': L('b_t'),
        }

        ex = L('ex_ey')
        props['centro_corte'] = {
            'ex': ex,
            'ey': ex,
            'xo': ex,
            'yo': ex,
            'ro': np.sqrt(2 * ex**2 + (Iv + Iz) / Ag) if Ag > 0 else 0.0,
            'H' : None,
        }

        props['disponibles'] = [
            'b', 't', 'Ag', 'Ix', 'rx', 'Iv', 'iv', 'Iz', 'J', 'Cw',
        ]

    # ------------------------------------------------------------------ #
    # PERFIL T: T, WT, MT, ST                                             #
    # ------------------------------------------------------------------ #
    elif familia == 'PERFIL_T':
        
        # Atajo para perfiles T
        T = lambda clave, default=0.0: _leer(perfil, clave, bd,
                                              mapa=_MAPA_PERFIL_T, default=default)
        
        props['basicas'] = {
            'd'   : T('d'),
            'bf'  : T('bf'),
            'Ag'  : T('area'),
            'Peso': T('peso'),
        }
        
        props['flexion'] = {
            'Ix': T('Ix'), 'Sx': T('Sx'), 'rx': T('rx'), 'Zx': T('Zx'),
            'Iy': T('Iy'), 'Sy': T('Sy'), 'ry': T('ry'), 'Zy': T('Zy'),
        }
        
        props['torsion'] = {'J': T('J'), 'Cw': T('Cw')}
        
        props['seccion'] = {
            'tf'    : T('tf'),
            'tw'    : T('tw') if bd == 'AISC' else 0.0,
            'bf_2tf': T('bf_2tf'),
            'd_tw'  : T('d_tw'),
        }
        
        # Centro de corte: perfiles T tienen excentricidad
        props['centro_corte'] = {
            'xo': 0.0,
            'yo': 0.0,
            'ro': 0.0,
            'H' : None,
        }
        
        props['disponibles'] = [
            'd', 'bf', 'tf', 'Ag', 'Ix', 'Iy', 'Sx', 'Sy', 
            'rx', 'ry', 'Zx', 'Zy', 'J', 'Cw',
        ]

    # ------------------------------------------------------------------ #
    # TUBOS CIRCULARES: TUBO CIRC., PIPE                                 #
    # ------------------------------------------------------------------ #
    elif familia == 'TUBO_CIRC':
        
        # Atajo para tubos
        Tb = lambda clave, default=0.0: _leer(perfil, clave, bd,
                                               mapa=_MAPA_TUBO, default=default)
        
        d  = Tb('d')     # diámetro exterior
        t  = Tb('t')     # espesor
        Ag = Tb('area')
        
        # Tubos circulares: Ix = Iy
        Ix = Tb('Ix')
        Sx = Tb('Sx')
        rx = Tb('rx')
        
        props['basicas'] = {
            'd'   : d,
            't'   : t,
            'Ag'  : Ag,
            'Peso': Tb('peso'),
        }
        
        props['flexion'] = {
            'Ix': Ix, 'Sx': Sx, 'rx': rx, 'Zx': Tb('Zx'),
            'Iy': Ix, 'Sy': Sx, 'ry': rx, 'Zy': Tb('Zx'),  # simétrico
        }
        
        props['torsion'] = {'J': Tb('J'), 'Cw': Tb('Cw')}
        
        props['seccion'] = {
            'd'  : d,
            't'  : t,
            'd_t': d / t if t > 0 else 0.0,
        }
        
        props['centro_corte'] = {
            'xo': 0.0,  # centroide = centro de corte
            'yo': 0.0,
            'ro': rx,   # para sección circular ro ≈ rx
            'H' : 1.0,  # sección doblemente simétrica
        }
        
        props['disponibles'] = [
            'd', 't', 'Ag', 'Ix', 'rx', 'J', 'Cw',
        ]

    # ------------------------------------------------------------------ #
    # TUBOS CUADRADOS: TUBO CUAD.                                        #
    # ------------------------------------------------------------------ #
    elif familia == 'TUBO_CUAD':
        
        Tb = lambda clave, default=0.0: _leer(perfil, clave, bd,
                                               mapa=_MAPA_TUBO, default=default)
        
        d  = Tb('d')     # lado del cuadrado
        t  = Tb('t')     # espesor
        Ag = Tb('area')
        
        # Tubos cuadrados: Ix = Iy
        Ix = Tb('Ix')
        Sx = Tb('Sx')
        rx = Tb('rx')
        
        props['basicas'] = {
            'd'   : d,
            't'   : t,
            'Ag'  : Ag,
            'Peso': Tb('peso'),
        }
        
        props['flexion'] = {
            'Ix': Ix, 'Sx': Sx, 'rx': rx, 'Zx': Tb('Zx'),
            'Iy': Ix, 'Sy': Sx, 'ry': rx, 'Zy': Tb('Zx'),  # simétrico
        }
        
        props['torsion'] = {'J': Tb('J'), 'Cw': Tb('Cw')}
        
        props['seccion'] = {
            'd'  : d,
            't'  : t,
            'd_t': d / t if t > 0 else 0.0,
        }
        
        props['centro_corte'] = {
            'xo': 0.0,
            'yo': 0.0,
            'ro': rx,
            'H' : 1.0,
        }
        
        props['disponibles'] = [
            'd', 't', 'Ag', 'Ix', 'rx', 'J', 'Cw',
        ]

    # ------------------------------------------------------------------ #
    # TUBOS RECTANGULARES: TUBO RECT.                                    #
    # ------------------------------------------------------------------ #
    elif familia == 'TUBO_RECT':
        
        Tb = lambda clave, default=0.0: _leer(perfil, clave, bd,
                                               mapa=_MAPA_TUBO, default=default)
        
        d  = Tb('d')     # altura
        bf = Tb('bf')    # ancho
        t  = Tb('t')     # espesor
        Ag = Tb('area')
        
        props['basicas'] = {
            'd'   : d,
            'bf'  : bf,
            't'   : t,
            'Ag'  : Ag,
            'Peso': Tb('peso'),
        }
        
        props['flexion'] = {
            'Ix': Tb('Ix'), 'Sx': Tb('Sx'), 'rx': Tb('rx'), 'Zx': Tb('Zx'),
            'Iy': Tb('Iy'), 'Sy': Tb('Sy'), 'ry': Tb('ry'), 'Zy': Tb('Zy'),
        }
        
        props['torsion'] = {'J': Tb('J'), 'Cw': Tb('Cw')}
        
        props['seccion'] = {
            'd'  : d,
            'bf' : bf,
            't'  : t,
            'd_t': d / t if t > 0 else 0.0,
        }
        
        props['centro_corte'] = {
            'xo': 0.0,
            'yo': 0.0,
            'ro': np.sqrt(Tb('rx')**2 + Tb('ry')**2),
            'H' : 1.0,
        }
        
        props['disponibles'] = [
            'd', 'bf', 't', 'Ag', 'Ix', 'Iy', 'Sx', 'Sy', 
            'rx', 'ry', 'Zx', 'Zy', 'J', 'Cw',
        ]

    else:
        raise ValueError(
            f"Tipo '{tipo}' no soportado. "
            f"Válidos: {[t for ts in FAMILIAS.values() for t in ts]}"
        )

    return props


# ============================================================================
# VERIFICACIÓN DE PROPIEDADES MÍNIMAS
# ============================================================================

_REQUERIDAS = {
    'DOBLE_T'   : ['d', 'bf', 'tf', 'tw', 'hw', 'Ag', 'Ix', 'Iy', 'rx', 'ry'],
    'CANAL'     : ['d', 'bf', 'tf', 'tw', 'hw', 'Ag', 'Ix', 'Iy', 'rx', 'ry'],
    'ANGULAR'   : ['b', 't', 'Ag', 'Ix', 'rx'],
    'PERFIL_T'  : ['d', 'bf', 'tf', 'Ag', 'Ix', 'Iy', 'rx', 'ry'],
    'TUBO_CIRC' : ['d', 't', 'Ag', 'Ix', 'rx'],
    'TUBO_CUAD' : ['d', 't', 'Ag', 'Ix', 'rx'],
    'TUBO_RECT' : ['d', 'bf', 't', 'Ag', 'Ix', 'Iy', 'rx', 'ry'],
}

_OPCIONALES_IMPORTANTES = {
    'DOBLE_T'   : ['J', 'Cw'],
    'CANAL'     : ['J', 'Cw', 'x', 'eo'],
    'ANGULAR'   : ['J', 'Cw'],
    'PERFIL_T'  : ['J', 'Cw'],
    'TUBO_CIRC' : ['J'],
    'TUBO_CUAD' : ['J'],
    'TUBO_RECT' : ['J'],
}


def verificar_propiedades(props: dict) -> dict:
    """
    Verificar que las propiedades mínimas estén disponibles.

    Returns dict: 'completo' [bool], 'faltantes' [list], 'advertencias' [list]
    """
    familia     = props.get('familia', 'DESCONOCIDA')
    disponibles = props.get('disponibles', [])
    resultado   = {'completo': True, 'faltantes': [], 'advertencias': []}

    for prop in _REQUERIDAS.get(familia, []):
        if prop not in disponibles:
            resultado['faltantes'].append(prop)
            resultado['completo'] = False

    for prop in _OPCIONALES_IMPORTANTES.get(familia, []):
        if prop not in disponibles:
            resultado['advertencias'].append(
                f"'{prop}' no disponible — puede limitar el cálculo."
            )

    return resultado


# ============================================================================
# DISPLAY EN UNIDADES CIRSOC
# ============================================================================
#
# Factores de conversión desde mm/mm²/mm⁴/mm⁶ → unidades CIRSOC
#
#   mm        → mm        × 1         (d, bf, tf, tw, hw, b, t)
#   mm²       → cm²       ÷ 100       (Ag)
#   mm⁴       → cm⁴       ÷ 1e4       (Ix, Iy, Iz, Iv, J)
#   mm³       → cm³       ÷ 1e3       (Sx, Sy, Zx, Zy, Sv)
#   mm(radio) → cm        ÷ 10        (rx, ry, iv, iz, ro)
#   mm⁶       → cm⁶       ÷ 1e6       (Cw)
#   mm(dist)  → cm        ÷ 10        (x, eo, ex-ey, ro)
#   kg/m      → kg/m      × 1         (Peso)

_DISPLAY_UNIDADES = {
    # Dimensiones
    'd'    : ('mm',    1.0),
    'bf'   : ('mm',    1.0),
    'tf'   : ('mm',    1.0),
    'tw'   : ('mm',    1.0),
    'hw'   : ('mm',    1.0),
    'b'    : ('mm',    1.0),
    't'    : ('mm',    1.0),
    # Sección y masa
    'Ag'   : ('cm²',   1/100),
    'Peso' : ('kg/m',  1.0),
    # Inercias
    'Ix'   : ('cm⁴',   1/1e4),
    'Iy'   : ('cm⁴',   1/1e4),
    'Iz'   : ('cm⁴',   1/1e4),
    'Iv'   : ('cm⁴',   1/1e4),
    'J'    : ('cm⁴',   1/1e4),
    # Módulos elásticos y plásticos
    'Sx'   : ('cm³',   1/1e3),
    'Sy'   : ('cm³',   1/1e3),
    'Zx'   : ('cm³',   1/1e3),
    'Zy'   : ('cm³',   1/1e3),
    'Sv'   : ('cm³',   1/1e3),
    # Radios de giro
    'rx'   : ('cm',    1/10),
    'ry'   : ('cm',    1/10),
    'iv'   : ('cm',    1/10),
    'iz'   : ('cm',    1/10),
    # Alabeo
    'Cw'   : ('cm⁶',   1/1e6),
    # Centro de corte / centroide
    'xo'   : ('cm',    1/10),
    'yo'   : ('cm',    1/10),
    'ro'   : ('cm',    1/10),
    'x'    : ('cm',    1/10),
    'eo'   : ('cm',    1/10),
    'ex'   : ('cm',    1/10),
    'ey'   : ('cm',    1/10),
    # Adimensionales
    'bf_2tf': ('—',    1.0),
    'hw_tw' : ('—',    1.0),
    'b_t'   : ('—',    1.0),
    'd_t'   : ('—',    1.0),
    'd_tw'  : ('—',    1.0),
    'H'     : ('—',    1.0),
}


def formatear_para_display(props: dict, decimales: int = 2) -> dict:
    """
    Convertir el dict de propiedades (en mm/mm²/mm⁴/mm⁶) a unidades CIRSOC
    para mostrar al usuario.

    Parámetros:
    -----------
    props     : dict — salida de extraer_propiedades()
    decimales : int  — cifras decimales en el redondeo (default: 2)

    Returns:
    --------
    dict con la misma estructura que props pero con:
        - valores convertidos a unidades CIRSOC
        - clave adicional 'unidades' con la unidad de cada propiedad
    """

    def _conv(clave, valor):
        """Convertir un valor según la tabla de unidades display.

        Fuerza a float nativo de Python para que reticulate
        no encuentre np.float32/float64 sin numpy importado en R.
        """
        if valor is None:
            return None, '—'
        # Aceptar numpy scalars y Python int/float
        try:
            valor = float(valor)
            if np.isnan(valor):
                return None, '—'
        except (TypeError, ValueError):
            return valor, '—'
        unidad, factor = _DISPLAY_UNIDADES.get(clave, ('—', 1.0))
        return round(float(valor * factor), decimales), unidad

    display = {
        'tipo'   : props['tipo'],
        'familia': props['familia'],
    }

    # Recorrer cada subdict y convertir
    for seccion in ('basicas', 'flexion', 'torsion', 'seccion', 'centro_corte'):
        display[seccion]           = {}
        display[f'{seccion}_uds'] = {}

        for clave, valor in props.get(seccion, {}).items():
            val_conv, unidad = _conv(clave, valor)
            display[seccion][clave]           = val_conv
            display[f'{seccion}_uds'][clave]  = unidad

    return display


def imprimir_propiedades(props: dict, decimales: int = 2):
    """
    Imprimir propiedades de un perfil en unidades CIRSOC.

    Parámetros:
    -----------
    props     : dict — salida de extraer_propiedades()
    decimales : int  — cifras decimales
    """
    d = formatear_para_display(props, decimales)

    titulo = f"PROPIEDADES — {d['tipo']}  ({d['familia']})"
    print()
    print("=" * 55)
    print(f"  {titulo}")
    print("=" * 55)

    secciones = {
        'basicas'      : 'Dimensiones y masa',
        'flexion'      : 'Propiedades de flexión',
        'torsion'      : 'Propiedades de torsión',
        'seccion'      : 'Relaciones de esbeltez',
        'centro_corte' : 'Centro de corte',
    }

    for sec, titulo_sec in secciones.items():
        datos = d.get(sec, {})
        uds   = d.get(f'{sec}_uds', {})
        if not datos:
            continue

        print(f"\n  {titulo_sec}")
        print("  " + "-" * 45)
        for clave, valor in datos.items():
            unidad = uds.get(clave, '—')
            if valor is None:
                continue
            print(f"    {clave:<12} = {str(valor):>12}  {unidad}")

    print("=" * 55)
    print()
