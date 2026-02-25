"""
test_utilidades_perfil.py
==========================
Script de prueba para validar utilidades_perfil con nuevos tipos de perfiles.
"""

import os
import sys

# Configurar rutas
sys.path.insert(0, '/home/claude')
os.environ['STEELCHECK_ROOT'] = 'C:\git\perfiles-verificacion'

from gestor_base_datos import GestorBaseDatos
from utilidades_perfil import (
    extraer_propiedades, 
    imprimir_propiedades,
    verificar_propiedades,
    FAMILIAS
)

def print_separator(title):
    """Separador visual para la consola."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_familias():
    """Test 1: Verificar definición de familias."""
    print_separator("TEST 1: Familias Definidas")
    
    for familia, tipos in FAMILIAS.items():
        print(f"\n{familia:15s}: {tipos}")

def test_perfil_tipo(gestor, tipo, nombre_perfil):
    """Helper para testear un perfil específico."""
    try:
        perfil = gestor.obtener_datos_perfil(nombre_perfil)
        props = extraer_propiedades(perfil, base_datos=gestor.nombre_base_activa())
        
        print(f"\n{tipo} - {nombre_perfil}")
        print(f"  Familia: {props['familia']}")
        print(f"  Propiedades básicas:")
        for k, v in props['basicas'].items():
            if v != 0.0:
                print(f"    {k:6s}: {v:.2f}")
        
        print(f"  Propiedades disponibles: {len(props['disponibles'])}")
        print(f"    {props['disponibles']}")
        
        # Verificar completitud
        verif = verificar_propiedades(props)
        if verif['completo']:
            print("  ✓ Propiedades completas")
        else:
            print(f"  ⚠️  Faltantes: {verif['faltantes']}")
        
        if verif['advertencias']:
            for adv in verif['advertencias']:
                print(f"  ⚠️  {adv}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error en {tipo} - {nombre_perfil}:")
        print(f"   {e}")
        return False

def test_nuevos_tipos_cirsoc(gestor):
    """Test 2: Perfiles nuevos en CIRSOC."""
    print_separator("TEST 2: Nuevos Tipos CIRSOC")
    
    gestor.cambiar_base('CIRSOC')
    
    tests = [
        ('Perfil T', 'T 3/4 x 3/4 x 1/8'),
        ('Tubo Circular', '12,7 x 0,7'),
        ('Tubo Cuadrado', '15 x 0,7'),
        ('Tubo Rectangular', '20 x 10 x 0,7'),
    ]
    
    resultados = []
    for tipo, nombre in tests:
        exitoso = test_perfil_tipo(gestor, tipo, nombre)
        resultados.append((tipo, exitoso))
    
    return resultados

def test_tipos_tradicionales(gestor):
    """Test 3: Tipos tradicionales (regresión)."""
    print_separator("TEST 3: Tipos Tradicionales (Regresión)")
    
    gestor.cambiar_base('CIRSOC')
    
    tests = [
        ('Doble T - W', '44X335'),
        ('Doble T - IPN', '80'),
        ('Canal - C', 'C15x50'),
        ('Angular - L', 'L 5/8 x 5/8 x 1/8'),
    ]
    
    resultados = []
    for tipo, nombre in tests:
        exitoso = test_perfil_tipo(gestor, tipo, nombre)
        resultados.append((tipo, exitoso))
    
    return resultados

def test_extraccion_completa(gestor):
    """Test 4: Extracción completa con imprimir_propiedades."""
    print_separator("TEST 4: Extracción Completa - Tubo Rectangular")
    
    gestor.cambiar_base('CIRSOC')
    
    try:
        perfil = gestor.obtener_datos_perfil('20 x 10 x 0,7')
        props = extraer_propiedades(perfil, base_datos='CIRSOC')
        imprimir_propiedades(props, decimales=3)
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_aisc_tubos(gestor):
    """Test 5: Tubos en AISC (PIPE y HSS)."""
    print_separator("TEST 5: Tubos AISC")
    
    gestor.cambiar_base('AISC')
    
    # Buscar ejemplos de PIPE y HSS
    db = gestor.obtener_base_activa()
    
    # PIPE
    pipes = db[db['Tipo'] == 'PIPE']
    if len(pipes) > 0:
        nombre_pipe = pipes['PERFIL'].iloc[0]
        print(f"\nTestear PIPE: {nombre_pipe}")
        test_perfil_tipo(gestor, 'PIPE', nombre_pipe)
    
    # HSS (puede ser cuadrado o rectangular)
    hss = db[db['Tipo'] == 'HSS']
    if len(hss) > 0:
        nombre_hss = hss['PERFIL'].iloc[0]
        print(f"\nTestear HSS: {nombre_hss}")
        test_perfil_tipo(gestor, 'HSS', nombre_hss)

def test_comparacion_cross_database(gestor):
    """Test 6: Comparación entre bases para perfil T."""
    print_separator("TEST 6: Comparación CIRSOC vs AISC - Perfil T")
    
    # CIRSOC - T
    gestor.cambiar_base('CIRSOC')
    try:
        perfil_c = gestor.obtener_datos_perfil('T 3/4 x 3/4 x 1/8')
        props_c = extraer_propiedades(perfil_c, 'CIRSOC')
        
        print("\nCIRSOC - T 3/4 x 3/4 x 1/8:")
        print(f"  Ag: {props_c['basicas']['Ag']:.2f} mm²")
        print(f"  Ix: {props_c['flexion']['Ix']:.0f} mm⁴")
        print(f"  Iy: {props_c['flexion']['Iy']:.0f} mm⁴")
    except Exception as e:
        print(f"  Error CIRSOC: {e}")
    
    # AISC - WT
    gestor.cambiar_base('AISC')
    try:
        db = gestor.obtener_base_activa()
        wt = db[db['Tipo'] == 'WT']
        if len(wt) > 0:
            nombre_wt = wt['PERFIL'].iloc[0]
            perfil_a = gestor.obtener_datos_perfil(nombre_wt)
            props_a = extraer_propiedades(perfil_a, 'AISC')
            
            print(f"\nAISC - {nombre_wt}:")
            print(f"  Ag: {props_a['basicas']['Ag']:.2f} mm²")
            print(f"  Ix: {props_a['flexion']['Ix']:.0f} mm⁴")
            print(f"  Iy: {props_a['flexion']['Iy']:.0f} mm⁴")
    except Exception as e:
        print(f"  Error AISC: {e}")

def main():
    """Ejecutar todos los tests."""
    print("\n" + "█"*70)
    print("█  TEST SUITE - utilidades_perfil.py con Nuevos Tipos")
    print("█"*70)
    
    try:
        # Inicializar gestor
        gestor = GestorBaseDatos(carpeta_datos='C:\git\perfiles-verificacion\database')
        
        # Test 1: Familias
        test_familias()
        
        # Test 2: Nuevos tipos CIRSOC
        resultados_nuevos = test_nuevos_tipos_cirsoc(gestor)
        
        # Test 3: Tipos tradicionales
        resultados_trad = test_tipos_tradicionales(gestor)
        
        # Test 4: Extracción completa
        test_extraccion_completa(gestor)
        
        # Test 5: AISC tubos
        test_aisc_tubos(gestor)
        
        # Test 6: Comparación cross-database
        test_comparacion_cross_database(gestor)
        
        # Resumen
        print_separator("RESUMEN")
        
        print("\nNuevos Tipos CIRSOC:")
        for tipo, exitoso in resultados_nuevos:
            estado = "✓" if exitoso else "❌"
            print(f"  {estado} {tipo}")
        
        print("\nTipos Tradicionales:")
        for tipo, exitoso in resultados_trad:
            estado = "✓" if exitoso else "❌"
            print(f"  {estado} {tipo}")
        
        todos_exitosos = all([e for _, e in resultados_nuevos + resultados_trad])
        
        if todos_exitosos:
            print("\n✓ Todos los tests completados exitosamente")
        else:
            print("\n⚠️  Algunos tests fallaron")
        
        print("\n" + "█"*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
