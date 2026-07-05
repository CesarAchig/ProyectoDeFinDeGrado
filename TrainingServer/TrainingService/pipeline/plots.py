#######################
#       Imports       #
#######################
from common.logger import CloudWatchLogger
import os
from pathlib import Path
from typing import Any
import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


###########################
#        Functions        #
###########################
def generar_graficos(modelo: Any, X_test: pd.DataFrame, y_test: pd.Series, tipo_problema: str, dataset: pd.DataFrame, directorio_salida: str) -> list:
    """
    Genera gráficos de evaluación del modelo según el tipo de problema.
    Args:
        modelo (Any): Modelo entrenado de sklearn.
        X_test (pd.DataFrame): Features de test (transformadas).
        y_test (pd.Series): Valores reales de la variable objetivo.
        tipo_problema (str): Tipo de problema ("classification" o "regression").
        dataset (pd.DataFrame): DataFrame original (para gráficos de distribución).
        directorio_salida (str): Ruta donde guardar los PNG generados.

    Returns:
        list: Lista de rutas absolutas de los gráficos generados.
    """
    Path(directorio_salida).mkdir(parents=True, exist_ok=True)
    graficos_generados = []

    CloudWatchLogger.get().info(f"[Plots] Generando gráficos complementarios para: {tipo_problema}")

    # 1. Feature Importance (común a ambos tipos)
    graficos_generados += _feature_importance(modelo, X_test, directorio_salida)

    # 2. Target Distribution
    graficos_generados += _target_distribution(dataset, directorio_salida, es_regresion=(tipo_problema == "regression"))

    # 3. Correlation Heatmap (común)
    graficos_generados += _graficos_comunes(dataset, directorio_salida)

    CloudWatchLogger.get().info(f"[Plots] Total de gráficos complementarios generados: {len(graficos_generados)}")
    return graficos_generados


def _feature_importance(modelo: Any, X_test: pd.DataFrame, directorio: str) -> list:
    """
    Genera gráfico de feature importance si el modelo lo soporta.
    Args:
        modelo (Any): Modelo entrenado de sklearn.
        X_test (pd.DataFrame): Features de test (transformadas).
        directorio (str): Ruta donde guardar los PNG generados.

    Returns:
        list: Lista de rutas absolutas de los gráficos generados.
    """
    generados = []
    try:
        if hasattr(modelo, "feature_importances_"):
            importancias = modelo.feature_importances_
            if hasattr(X_test, "columns"):
                nombres = X_test.columns
            else:
                nombres = [f"Feature_{i}" for i in range(len(importancias))]

            indices = np.argsort(importancias)[::-1][:20]
            plt.figure(figsize=(10, 8))
            plt.barh(range(len(indices)), importancias[indices][::-1], color="steelblue")
            plt.yticks(range(len(indices)), [nombres[i] for i in indices[::-1]])
            plt.xlabel("Importancia")
            plt.title("Feature Importance (Top 20)")
            ruta = os.path.join(directorio, "feature_importance.png")
            plt.tight_layout()
            plt.savefig(ruta, dpi=100, bbox_inches="tight")
            plt.close()
            generados.append(ruta)
            CloudWatchLogger.get().info("  [OK] Feature importance guardada.")
    except Exception as error:
        CloudWatchLogger.get().warning(f"  [FAIL] Error en feature importance: {error}")
    return generados


def _graficos_comunes(dataset: pd.DataFrame, directorio: str) -> list:
    """
    Genera gráficos comunes a cualquier tipo de problema
    Args:
        dataset (pd.DataFrame): DataFrame original (para gráficos de distribución).
        directorio (str): Ruta donde guardar los PNG generados.

    Returns:
        list: Lista de rutas absolutas de los gráficos generados.
    """
    generados = []

    # Correlation Heatmap
    try:
        columnas_numericas = dataset.select_dtypes(include=[np.number]).columns
        if len(columnas_numericas) > 1:
            correlacion = dataset[columnas_numericas].corr()
            plt.figure(figsize=(12, 10))
            sns.heatmap(
                correlacion,
                annot=True,
                fmt=".2f",
                cmap="coolwarm",
                center=0,
                square=True,
                linewidths=0.5,
            )
            plt.title("Mapa de Calor de Correlaciones")
            ruta = os.path.join(directorio, "correlation_heatmap.png")
            plt.tight_layout()
            plt.savefig(ruta, dpi=100, bbox_inches="tight")
            plt.close()
            generados.append(ruta)
            CloudWatchLogger.get().info("  [OK] Mapa de calor de correlaciones guardado.")
        else:
            CloudWatchLogger.get().info("  - No hay suficientes columnas numéricas para correlation heatmap.")
    except Exception as error:
        CloudWatchLogger.get().warning(f"  [FAIL] Error en correlation heatmap: {error}")

    return generados


def _target_distribution(dataset: pd.DataFrame, directorio: str, es_regresion: bool = False) -> list:
    """
    Genera gráfico de distribución de la variable objetivo.
    Args:
        dataset (pd.DataFrame): DataFrame original (para gráficos de distribución).
        directorio (str): Ruta donde guardar los PNG generados.
        es_regresion (bool, optional): Indica si el problema es de regresión (histograma) o clasificación (countplot). Defaults to False.

    Returns:
        list: Lista de rutas absolutas de los gráficos generados.
    """
    generados = []

    try:
        # Buscar la columna target
        # También buscar columnas con nombre 'target' o la última columna
        columna_target = None
        for candidata in ["target", "class", "label", "y"]:
            if candidata in dataset.columns:
                columna_target = candidata
                break
        if columna_target is None:
            columna_target = dataset.columns[-1]

        plt.figure(figsize=(10, 6))

        if es_regresion:
            # Histograma para regresión
            plt.hist(dataset[columna_target].dropna(), bins=30, edgecolor="k", alpha=0.7, color="steelblue")
            plt.xlabel(columna_target)
            plt.ylabel("Frecuencia")
            plt.title(f"Distribución de {columna_target} (Target)")
        else:
            # Countplot para clasificación
            conteos = dataset[columna_target].value_counts()
            plt.bar(conteos.index.astype(str), conteos.values, color="steelblue", edgecolor="k")
            plt.xlabel(columna_target)
            plt.ylabel("Número de muestras")
            plt.title(f"Distribución de Clases: {columna_target}")

        ruta = os.path.join(directorio, "target_distribution.png")
        plt.tight_layout()
        plt.savefig(ruta, dpi=100, bbox_inches="tight")
        plt.close()
        generados.append(ruta)
        CloudWatchLogger.get().info("  [OK] Distribución de target guardada.")
    except Exception as error:
        CloudWatchLogger.get().warning(f"  [FAIL] Error en target distribution: {error}")

    return generados
