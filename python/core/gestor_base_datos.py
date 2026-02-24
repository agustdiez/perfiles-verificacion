"""
gestor_base_datos.py
====================
Gestor de bases de datos de perfiles estructurales.

Bases de datos soportadas:
    - CIRSOC : cirsoc-shapes-database.csv
    - AISC   : perfiles_SI.csv

Unidades almacenadas en la BD:
    Dimensiones : mm
    Áreas       : cm²
    Inercias    : cm⁴
    Módulos     : cm³
    Radios      : cm
    J, Cw       : cm⁴ / cm⁶
"""

import os
import pandas as pd
import numpy as np


class GestorBaseDatos:
    """Gestor de bases de datos de perfiles estructurales."""

    def __init__(self, carpeta_datos=None):
        """
        Parámetros:
        -----------
        carpeta_datos : str, opcional
            Ruta a la carpeta con los CSV.
            Si es None, se resuelve automáticamente:
                1. Variable de entorno STEELCHECK_ROOT  → <raíz>/database
                2. Ruta relativa a este archivo         → ../../database
                   (python/core/ → python/ → raíz/ → database/)
        """
        if carpeta_datos is None:
            raiz_env = os.environ.get('STEELCHECK_ROOT', None)
            if raiz_env:
                self.carpeta_datos = os.path.join(raiz_env, 'database')
            else:
                _este_archivo = os.path.abspath(__file__)
                _carpeta      = os.path.dirname(_este_archivo)        # python/core/
                self.carpeta_datos = os.path.normpath(
                    os.path.join(_carpeta, '..', '..', 'database')    # raíz/database/
                )
        else:
            self.carpeta_datos = carpeta_datos

        self.db_aisc   = None
        self.db_cirsoc = None
        self.db_activa = 'CIRSOC'
        self._cargar_bases_de_datos()

    # ------------------------------------------------------------------ #
    # CARGA                                                               #
    # ------------------------------------------------------------------ #

    def _cargar_bases_de_datos(self):
        """Cargar ambas bases de datos desde CSV."""

        # na_values: '-' cubre los valores vacíos tipográficos de ambas BDs.
        _na = ['-']

        # En pandas 3.x, pd.to_numeric con errors='ignore' fue removido.
        # Se convierte columna por columna intentando numérico; si falla, se deja como está.
        def _convertir_numericas(df: pd.DataFrame) -> pd.DataFrame:
            for col in df.columns:
                try:
                    convertida = pd.to_numeric(df[col], errors='coerce')
                    # Solo reemplazar si la columna tenía mayoría de valores numéricos
                    # (evita convertir columnas de texto como PERFIL, Tipo)
                    if convertida.notna().sum() > df[col].notna().sum() * 0.3:
                        df[col] = convertida
                except Exception:
                    pass
            return df

        # AISC
        try:
            ruta = os.path.join(self.carpeta_datos, 'perfiles_SI.csv')
            self.db_aisc = pd.read_csv(ruta, na_values=_na)
            self.db_aisc.columns = self.db_aisc.columns.str.strip()
            self.db_aisc = _convertir_numericas(self.db_aisc)
            print(f"✓ AISC cargada: {len(self.db_aisc)} perfiles")
            print(f"  Familias: {sorted(self.db_aisc['Tipo'].unique().tolist())}")
        except Exception as e:
            print(f"⚠️  Error al cargar AISC: {e}")
            self.db_aisc = pd.DataFrame()

        # CIRSOC
        try:
            ruta = os.path.join(self.carpeta_datos, 'cirsoc-shapes-database.csv')
            self.db_cirsoc = pd.read_csv(ruta, na_values=_na)
            self.db_cirsoc.columns = self.db_cirsoc.columns.str.strip()
            self.db_cirsoc = _convertir_numericas(self.db_cirsoc)
            print(f"✓ CIRSOC cargada: {len(self.db_cirsoc)} perfiles")
            print(f"  Familias: {sorted(self.db_cirsoc['Tipo'].unique().tolist())}")
        except Exception as e:
            print(f"⚠️  Error al cargar CIRSOC: {e}")
            self.db_cirsoc = pd.DataFrame()

    # ------------------------------------------------------------------ #
    # SELECCIÓN DE BASE ACTIVA                                            #
    # ------------------------------------------------------------------ #

    def cambiar_base(self, nombre: str):
        """
        Cambiar la base de datos activa.

        Parámetros:
        -----------
        nombre : 'AISC' | 'CIRSOC'
        """
        nombre = nombre.upper()
        if nombre not in ('AISC', 'CIRSOC'):
            raise ValueError("La base de datos debe ser 'AISC' o 'CIRSOC'.")
        self.db_activa = nombre
        print(f"✓ Base de datos activa: {self.db_activa}")

    def obtener_base_activa(self) -> pd.DataFrame:
        """Retornar copia de la base de datos activa."""
        if self.db_activa == 'AISC':
            return self.db_aisc.copy()
        return self.db_cirsoc.copy()

    def nombre_base_activa(self) -> str:
        return self.db_activa

    # ------------------------------------------------------------------ #
    # CONSULTAS                                                           #
    # ------------------------------------------------------------------ #

    def obtener_familias(self) -> list:
        """Listar familias disponibles en la base activa."""
        db = self.obtener_base_activa()
        if 'Tipo' in db.columns:
            return sorted(db['Tipo'].dropna().unique().tolist())
        return []

    def obtener_perfiles_por_familia(self, familia: str) -> list:
        """Listar perfiles de una familia específica."""
        db = self.obtener_base_activa()
        if 'Tipo' in db.columns:
            return sorted(db[db['Tipo'] == familia]['PERFIL'].tolist())
        return []

    def obtener_datos_perfil(self, nombre_perfil: str) -> pd.Series:
        """
        Retornar fila completa de un perfil.

        Raises:
        -------
        ValueError si el perfil no existe.
        """
        db = self.obtener_base_activa()
        try:
            return db[db['PERFIL'] == nombre_perfil].iloc[0]
        except IndexError:
            raise ValueError(
                f"Perfil '{nombre_perfil}' no encontrado en {self.db_activa}."
            )

    def obtener_resumen_perfil(self, nombre_perfil: str) -> dict | None:
        """
        Retornar resumen básico de un perfil para mostrar en UI.
        Valores en unidades CIRSOC: Ag [cm²], d/bf [mm], Peso [kg/m].
        """
        try:
            p            = self.obtener_datos_perfil(nombre_perfil)
            col_peso     = 'W'    if self.db_activa == 'AISC' else 'Peso'
            col_area     = 'A'    if self.db_activa == 'AISC' else 'Ag'
            # AISC: A en mm² → convertir a cm²
            area_raw     = p.get(col_area, np.nan)
            area_cm2     = area_raw / 100 if self.db_activa == 'AISC' else area_raw
            return {
                'nombre'  : nombre_perfil,
                'tipo'    : p.get('Tipo', 'N/A'),
                'peso'    : p.get(col_peso, np.nan),   # kg/m
                'area'    : area_cm2,                  # cm²
                'altura'  : p.get('d',  np.nan),       # mm
                'ancho'   : p.get('bf', np.nan),       # mm
            }
        except Exception:
            return None

    def buscar_perfiles(self, criterio: str,
                        valor_min=None, valor_max=None) -> pd.DataFrame:
        """
        Filtrar perfiles por criterio numérico o por familia.

        Ejemplos:
            buscar_perfiles('Tipo', valor_min='W')
            buscar_perfiles('d',  valor_min=300, valor_max=500)
            buscar_perfiles('Ag', valor_min=50)
        """
        db = self.obtener_base_activa()
        if criterio == 'Tipo':
            if valor_min is not None:
                return db[db['Tipo'] == valor_min].copy()
        elif criterio in db.columns:
            res = db.copy()
            if valor_min is not None:
                res = res[res[criterio] >= valor_min]
            if valor_max is not None:
                res = res[res[criterio] <= valor_max]
            return res
        return pd.DataFrame()

    def estadisticas(self) -> dict:
        """Estadísticas básicas de la base activa. Peso en kg/m, altura en mm."""
        db       = self.obtener_base_activa()
        col_peso = 'W' if self.db_activa == 'AISC' else 'Peso'
        return {
            'total_perfiles': len(db),
            'familias'      : db['Tipo'].nunique() if 'Tipo' in db.columns else 0,
            'peso_min'      : db[col_peso].min() if col_peso in db.columns else np.nan,
            'peso_max'      : db[col_peso].max() if col_peso in db.columns else np.nan,
            'altura_min'    : db['d'].min() if 'd' in db.columns else np.nan,
            'altura_max'    : db['d'].max() if 'd' in db.columns else np.nan,
        }
