#######################
#       Imports       #
#######################
from common.logger import CloudWatchLogger
from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd


###########################
#        Functions        #
###########################
def entrenar_modelo(X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame, y_test: pd.Series, nombre_algoritmo: str, hiperparametros: dict, tipo_problema: str) -> Tuple[Any, Dict[str, float]]:
    """
    Entrena un modelo de scikit-learn usando el algoritmo recomendado.
    Args:
        X_train (pd.DataFrame): Features de entrenamiento (ya preprocesadas).
        y_train (pd.Series): Variable objetivo de entrenamiento.
        X_test (pd.DataFrame): Features de test (ya preprocesadas).
        y_test (pd.Series): Variable objetivo de test.
        nombre_algoritmo (str): Nombre exacto de la clase sklearn.
        hiperparametros (dict): Diccionario de hiperparámetros para el modelo.
        tipo_problema (str): "classification" o "regression".

    Returns:
        Tuple[Any, Dict[str, float]]: Tupla con (modelo_entrenado, diccionario_de_métricas).
    """
    
    # Se busca el algoritmo en los módulos permitidos.
    clase_modelo = _buscar_algoritmo(nombre_algoritmo)

    # Instanciar y entrenar el modelo.
    CloudWatchLogger.get().info(
        f"[Train] Entrenando modelo: {nombre_algoritmo} con hiperparámetros: {hiperparametros}",
    )

    try:
        modelo = clase_modelo(**hiperparametros)
    except TypeError as error:
        CloudWatchLogger.get().warning(
            f"[Train] Error al instanciar {nombre_algoritmo} con los hiperparámetros dados: {error}. "
            "Reintentando con valores por defecto.",
        )
        modelo = clase_modelo()

    modelo.fit(X_train, y_train)
    CloudWatchLogger.get().info(f"[Train] Modelo entrenado exitosamente: {type(modelo).__name__}")

    # Se realizan predicciones sobre el conjunto de test.
    y_pred = modelo.predict(X_test)
    CloudWatchLogger.get().info(f"[Train] Predicciones generadas: {len(y_pred)} muestras")

    # Se calculan las métricas según el tipo de problema.
    metricas = _calcular_metricas(y_test, y_pred, tipo_problema)

    CloudWatchLogger.get().info("[Train] Métricas calculadas:")
    for nombre, valor in metricas.items():
        CloudWatchLogger.get().info(f"[Train]   {nombre}: {valor:.4f}")

    return modelo, metricas


def _buscar_algoritmo(nombre_algoritmo: str) -> type:
    """
    Busca de forma segura una clase de algoritmo en módulos sklearn predefinidos.
    Solo se permite búsqueda en: ensemble, linear_model, neighbors, svm, tree.
    Args:
        nombre_algoritmo (str): Nombre exacto de la clase (ej: "RandomForestClassifier").

    Raises:
        ValueError: Si el algoritmo no se encuentra en los módulos permitidos.

    Returns:
        type: La clase del algoritmo encontrada.
    """
    from sklearn import ensemble, linear_model, neighbors, svm, tree

    MODULOS_PERMITIDOS = [
        ensemble,
        linear_model,
        neighbors,
        svm,
        tree,
    ]

    for modulo in MODULOS_PERMITIDOS:
        if hasattr(modulo, nombre_algoritmo):
            clase = getattr(modulo, nombre_algoritmo)
            CloudWatchLogger.get().info(
                f"[Train] Algoritmo '{nombre_algoritmo}' encontrado en módulo '{modulo.__name__}'.",
            )
            return clase

    # No encontrado en ningún módulo permitido
    mensaje = (
        f"Algoritmo '{nombre_algoritmo}' no encontrado en los módulos sklearn permitidos: "
        f"ensemble, linear_model, neighbors, svm, tree."
    )
    CloudWatchLogger.get().error(mensaje)
    raise ValueError(mensaje)


def _calcular_metricas(y_test: pd.Series, y_pred: np.ndarray, tipo_problema: str) -> Dict[str, float]:
    """
    Calcula métricas de rendimiento según el tipo de problema.
    Args:
        y_test (pd.Series): Valores reales de la variable objetivo.
        y_pred (np.ndarray): Valores predichos por el modelo.
        tipo_problema (str): "classification" o "regression".

    Returns:
        Dict[str, float]: Diccionario con nombre de métrica -> valor.
    """
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        mean_absolute_error,
        mean_squared_error,
        precision_score,
        r2_score,
        recall_score,
    )

    metricas: Dict[str, float] = {}

    if tipo_problema == "classification":
        # Métricas de clasificación con average='weighted' para multiclase
        metricas["accuracy"] = float(accuracy_score(y_test, y_pred))
        metricas["precision"] = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        metricas["recall"] = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        metricas["f1"] = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

    elif tipo_problema == "regression":
        # Métricas de regresión
        mse = float(mean_squared_error(y_test, y_pred))
        metricas["mse"] = mse
        metricas["rmse"] = float(np.sqrt(mse))
        metricas["mae"] = float(mean_absolute_error(y_test, y_pred))
        metricas["r2"] = float(r2_score(y_test, y_pred))

    else:
        CloudWatchLogger.get().warning(
            f"[Train] Tipo de problema desconocido: '{tipo_problema}'. Calculando solo métricas básicas.",
        )
        # Intentar ambas si es posible
        try:
            metricas["accuracy"] = float(accuracy_score(y_test, y_pred))
        except Exception:
            pass
        try:
            mse = float(mean_squared_error(y_test, y_pred))
            metricas["mse"] = mse
            metricas["rmse"] = float(np.sqrt(mse))
            metricas["mae"] = float(mean_absolute_error(y_test, y_pred))
            metricas["r2"] = float(r2_score(y_test, y_pred))
        except Exception:
            pass

    return metricas
