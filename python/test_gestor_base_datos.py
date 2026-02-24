"""
test_gestor_base_datos.py
=========================
Pruebas funcionales para GestorBaseDatos.

Ejecutar desde la raíz del proyecto:
    python python/test_gestor_base_datos.py

O desde la carpeta python/:
    python test_gestor_base_datos.py
"""

import sys
import os

# Asegurar que python/ esté en el path
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from core.gestor_base_datos import GestorBaseDatos


# ============================================================================
# HELPERS
# ============================================================================

def separador(titulo):
    print(f"\n{'=' * 60}")
    print(f"  {titulo}")
    print('=' * 60)

def ok(msg):
    print(f"  ✅  {msg}")

def error(msg):
    print(f"  ❌  {msg}")

def info(msg):
    print(f"  ℹ️   {msg}")


# ============================================================================
# PRUEBAS
# ============================================================================

def test_carga(db):
    separador("TEST 1 — Carga de bases de datos")

    if db.db_cirsoc is not None and len(db.db_cirsoc) > 0:
        ok(f"CIRSOC cargada con {len(db.db_cirsoc)} perfiles")
    else:
        error("CIRSOC no cargada o vacía")

    if db.db_aisc is not None and len(db.db_aisc) > 0:
        ok(f"AISC cargada con {len(db.db_aisc)} perfiles")
    else:
        error("AISC no cargada o vacía")


def test_cambio_base(db):
    separador("TEST 2 — Cambio de base activa")

    db.cambiar_base('CIRSOC')
    assert db.nombre_base_activa() == 'CIRSOC'
    ok("Cambio a CIRSOC correcto")

    db.cambiar_base('AISC')
    assert db.nombre_base_activa() == 'AISC'
    ok("Cambio a AISC correcto")

    try:
        db.cambiar_base('OTRA')
        error("Debería haber lanzado ValueError con base inválida")
    except ValueError:
        ok("Rechazo correcto de base inválida")

    db.cambiar_base('CIRSOC')   # volver a CIRSOC para los siguientes tests


def test_familias(db):
    separador("TEST 3 — Familias disponibles")

    db.cambiar_base('CIRSOC')
    familias = db.obtener_familias()
    info(f"Familias CIRSOC: {familias}")

    esperadas = ['W', 'C', 'L', 'UPN']
    for f in esperadas:
        if f in familias:
            ok(f"Familia '{f}' presente")
        else:
            error(f"Familia '{f}' NO encontrada")


def test_perfiles_por_familia(db):
    separador("TEST 4 — Perfiles por familia")

    db.cambiar_base('CIRSOC')

    for familia in ['W', 'C', 'L']:
        perfiles = db.obtener_perfiles_por_familia(familia)
        if len(perfiles) > 0:
            ok(f"Familia '{familia}': {len(perfiles)} perfiles — primeros 3: {perfiles[:3]}")
        else:
            error(f"Familia '{familia}': sin perfiles")


def test_obtener_perfil(db):
    separador("TEST 5 — Obtener datos de perfil específico")

    db.cambiar_base('CIRSOC')
    familias = db.obtener_familias()

    # Tomar el primer perfil de la primera familia disponible
    if familias:
        familia_test = familias[0]
        perfiles     = db.obtener_perfiles_por_familia(familia_test)
        if perfiles:
            nombre = perfiles[0]
            try:
                datos = db.obtener_datos_perfil(nombre)
                ok(f"Perfil '{nombre}' obtenido — tipo: {datos.get('Tipo', '?')}")
            except Exception as e:
                error(f"Error al obtener '{nombre}': {e}")

    # Perfil inexistente
    try:
        db.obtener_datos_perfil('PERFIL_INVENTADO_XYZ')
        error("Debería haber lanzado ValueError")
    except ValueError:
        ok("Rechazo correcto de perfil inexistente")


def test_resumen_perfil(db):
    separador("TEST 6 — Resumen de perfil")

    db.cambiar_base('CIRSOC')
    perfiles_W = db.obtener_perfiles_por_familia('W')

    if perfiles_W:
        nombre  = perfiles_W[0]
        resumen = db.obtener_resumen_perfil(nombre)
        if resumen:
            ok(f"Resumen de '{nombre}':")
            for k, v in resumen.items():
                info(f"  {k:<25} = {v}")
        else:
            error(f"Resumen de '{nombre}' devolvió None")

    # Perfil inexistente — debe devolver None, no romper
    resumen_nulo = db.obtener_resumen_perfil('PERFIL_XYZ')
    if resumen_nulo is None:
        ok("Resumen de perfil inexistente devuelve None correctamente")
    else:
        error("Resumen de perfil inexistente debería devolver None")


def test_busqueda(db):
    separador("TEST 7 — Búsqueda de perfiles")

    db.cambiar_base('CIRSOC')

    # Por familia
    resultado = db.buscar_perfiles('Tipo', valor_min='W')
    if len(resultado) > 0:
        ok(f"Búsqueda por Tipo='W': {len(resultado)} perfiles")
    else:
        error("Búsqueda por Tipo='W' no arrojó resultados")

    # Por rango numérico — altura entre 200 y 400 mm
    resultado = db.buscar_perfiles('d', valor_min=200, valor_max=400)
    if len(resultado) > 0:
        ok(f"Búsqueda d=[200, 400] mm: {len(resultado)} perfiles")
        info(f"  Rango d obtenido: {resultado['d'].min():.0f} – {resultado['d'].max():.0f} mm")
    else:
        error("Búsqueda por altura no arrojó resultados")

    # Criterio inexistente — debe devolver DataFrame vacío
    resultado = db.buscar_perfiles('columna_inexistente')
    if len(resultado) == 0:
        ok("Criterio inexistente devuelve DataFrame vacío")
    else:
        error("Criterio inexistente debería devolver DataFrame vacío")


def test_estadisticas(db):
    separador("TEST 8 — Estadísticas")

    for base in ['CIRSOC', 'AISC']:
        db.cambiar_base(base)
        stats = db.estadisticas()
        ok(f"Estadísticas {base}:")
        for k, v in stats.items():
            info(f"  {k:<20} = {v}")


# ============================================================================
# EJECUCIÓN
# ============================================================================

if __name__ == '__main__':

    print("\n" + "=" * 60)
    print("  PRUEBAS — GestorBaseDatos")
    print("=" * 60)

    db = GestorBaseDatos()

    test_carga(db)
    test_cambio_base(db)
    test_familias(db)
    test_perfiles_por_familia(db)
    test_obtener_perfil(db)
    test_resumen_perfil(db)
    test_busqueda(db)
    test_estadisticas(db)

    print("\n" + "=" * 60)
    print("  Pruebas finalizadas")
    print("=" * 60 + "\n")
