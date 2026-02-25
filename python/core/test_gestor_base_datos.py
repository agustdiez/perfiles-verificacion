"""
test_gestor_base_datos.py
==========================
Script de prueba para validar el GestorBaseDatos actualizado.
"""

import os
os.environ['STEELCHECK_ROOT'] = 'C:\git\perfiles-verificacion'

from gestor_base_datos import GestorBaseDatos
import pandas as pd

def print_separator(title):
    """Separador visual para la consola."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_carga_bases():
    """Test 1: Verificar carga de ambas bases de datos."""
    print_separator("TEST 1: Carga de Bases de Datos")
    
    gestor = GestorBaseDatos(carpeta_datos='C:\git\perfiles-verificacion\database')
    
    # Verificar CIRSOC
    gestor.cambiar_base('CIRSOC')
    stats_cirsoc = gestor.estadisticas()
    print(f"\n✓ CIRSOC: {stats_cirsoc['total_perfiles']} perfiles")
    print(f"  Familias ({stats_cirsoc['familias']}): {gestor.obtener_familias()}")
    
    # Verificar AISC
    gestor.cambiar_base('AISC')
    stats_aisc = gestor.estadisticas()
    print(f"\n✓ AISC: {stats_aisc['total_perfiles']} perfiles")
    print(f"  Familias ({stats_aisc['familias']}): {gestor.obtener_familias()}")
    
    return gestor

def test_tipos_perfiles(gestor):
    """Test 2: Verificar diferentes tipos de perfiles."""
    print_separator("TEST 2: Tipos de Perfiles CIRSOC")
    
    gestor.cambiar_base('CIRSOC')
    
    # Ejemplos de cada tipo (con nombres correctos de CIRSOC)
    ejemplos = {
        'W': '44X335',              # Sin el prefijo W en el nombre
        'IPN': '80',                # Solo número
        'IPB': '100',               # Solo número
        'L': 'L 5/8 x 5/8 x 1/8',  # Con nombre completo
        'C': 'C15x50',              # Con nombre completo
        'TUBO CIRC.': '12,7 x 0,7', # Con dimensiones
    }
    
    for tipo in ejemplos.keys():
        perfiles = gestor.obtener_perfiles_por_familia(tipo)
        if perfiles:
            # Tomar el primer perfil o el especificado
            perfil_test = ejemplos[tipo] if ejemplos[tipo] else perfiles[0]
            
            try:
                resumen = gestor.obtener_resumen_perfil(perfil_test)
                datos = gestor.obtener_datos_perfil(perfil_test)
                
                print(f"\n{tipo} - {perfil_test}")
                print(f"  Peso: {resumen['peso']:.2f} kg/m")
                print(f"  Área: {resumen['area']:.2f} cm²")
                print(f"  Dimensiones: {resumen['altura']} x {resumen['ancho']}")
                
                # Mostrar columnas disponibles con valores no nulos
                cols_con_datos = [col for col in datos.index 
                                 if pd.notna(datos[col]) and col not in ['Tipo', 'PERFIL']]
                print(f"  Columnas con datos: {len(cols_con_datos)}")
                
            except Exception as e:
                print(f"\n⚠️  Error en {tipo}: {e}")

def test_propiedades_especificas(gestor):
    """Test 3: Verificar propiedades geométricas específicas."""
    print_separator("TEST 3: Propiedades Geométricas")
    
    gestor.cambiar_base('CIRSOC')
    
    # Perfil W con todas las propiedades
    perfil_w = gestor.obtener_datos_perfil('44X335')
    
    print("\nPerfil W 44X335 - Propiedades principales:")
    propiedades = ['d', 'bf', 'tf', 'tw-r1', 'Ag', 'Peso', 
                   'Ix', 'Sx', 'rx', 'Zx', 
                   'Iy', 'Sy', 'ry', 'Zy', 
                   'J', 'Cw']
    
    for prop in propiedades:
        if prop in perfil_w.index:
            valor = perfil_w[prop]
            if pd.notna(valor):
                print(f"  {prop:10s}: {valor}")

def test_busquedas(gestor):
    """Test 4: Verificar búsquedas y filtros."""
    print_separator("TEST 4: Búsquedas y Filtros")
    
    gestor.cambiar_base('CIRSOC')
    
    # Buscar perfiles W
    print("\nPerfiles W (primeros 5):")
    perfiles_w = gestor.buscar_perfiles('Tipo', valor_min='W')
    print(f"  Total encontrados: {len(perfiles_w)}")
    if len(perfiles_w) > 0:
        print(f"  Muestra: {perfiles_w['PERFIL'].head().tolist()}")
    
    # Buscar por peso
    print("\nPerfiles con peso < 10 kg/m:")
    perfiles_ligeros = gestor.buscar_perfiles('Peso', valor_max=10)
    print(f"  Total encontrados: {len(perfiles_ligeros)}")
    if len(perfiles_ligeros) > 0:
        print(f"  Tipos: {perfiles_ligeros['Tipo'].unique().tolist()}")

def test_columnas_nuevas(gestor):
    """Test 5: Verificar columnas nuevas específicas."""
    print_separator("TEST 5: Columnas Nuevas en CIRSOC")
    
    gestor.cambiar_base('CIRSOC')
    db = gestor.obtener_base_activa()
    
    # Columnas de análisis estructural
    columnas_estructurales = ['Lp_alma', 'Lr_alma', 'Lp_ala', 'Lr_ala', 
                              'X1', 'X2 (10)-5', 'd/tw']
    
    print("\nColumnas de análisis estructural disponibles:")
    for col in columnas_estructurales:
        if col in db.columns:
            no_nulos = db[col].notna().sum()
            print(f"  {col:15s}: {no_nulos:4d} valores no nulos")

def test_comparacion_bases(gestor):
    """Test 6: Comparar perfiles entre CIRSOC y AISC."""
    print_separator("TEST 6: Comparación CIRSOC vs AISC")
    
    # Perfil común
    perfil_cirsoc = '44X335'
    perfil_aisc = 'W44X335'
    
    # CIRSOC
    gestor.cambiar_base('CIRSOC')
    try:
        datos_cirsoc = gestor.obtener_datos_perfil(perfil_cirsoc)
        print(f"\nCIRSOC - {perfil_cirsoc}:")
        print(f"  Peso: {datos_cirsoc['Peso']:.2f} kg/m")
        print(f"  Ag:   {datos_cirsoc['Ag']:.2f} cm²")
        print(f"  Ix:   {datos_cirsoc['Ix']:.0f} cm⁴")
        print(f"  Iy:   {datos_cirsoc['Iy']:.0f} cm⁴")
    except Exception as e:
        print(f"\n⚠️  {perfil_cirsoc} no encontrado en CIRSOC: {e}")
    
    # AISC
    gestor.cambiar_base('AISC')
    try:
        datos_aisc = gestor.obtener_datos_perfil(perfil_aisc)
        print(f"\nAISC - {perfil_aisc}:")
        print(f"  W:    {datos_aisc['W']:.2f} kg/m")
        print(f"  A:    {datos_aisc['A']/100:.2f} cm²")  # mm² → cm²
        print(f"  Ix:   {datos_aisc['Ix']:.0f} cm⁴")
        print(f"  Iy:   {datos_aisc['Iy']:.0f} cm⁴")
        
        # Calcular diferencias
        print(f"\nDiferencias relativas:")
        if 'datos_cirsoc' in locals():
            diff_peso = abs(datos_cirsoc['Peso'] - datos_aisc['W']) / datos_cirsoc['Peso'] * 100
            print(f"  Peso: {diff_peso:.2f}%")
    except Exception as e:
        print(f"\n⚠️  Error en AISC: {e}")

def main():
    """Ejecutar todos los tests."""
    print("\n" + "█"*70)
    print("█  TEST SUITE - GestorBaseDatos Actualizado")
    print("█"*70)
    
    try:
        # Test 1: Carga
        gestor = test_carga_bases()
        
        # Test 2: Tipos de perfiles
        test_tipos_perfiles(gestor)
        
        # Test 3: Propiedades específicas
        test_propiedades_especificas(gestor)
        
        # Test 4: Búsquedas
        test_busquedas(gestor)
        
        # Test 5: Columnas nuevas
        test_columnas_nuevas(gestor)
        
        # Test 6: Comparación entre bases
        test_comparacion_bases(gestor)
        
        print_separator("RESUMEN")
        print("\n✓ Todos los tests completados exitosamente")
        print("\n" + "█"*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
