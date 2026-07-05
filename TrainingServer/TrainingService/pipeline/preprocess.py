#######################
#       Imports       #
#######################
from common.logger import CloudWatchLogger
from typing import List, Optional, Tuple
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


###########################
#        Functions        #
###########################
def preprocesar_datos(dataset: pd.DataFrame, resultado_eda: dict, random_state: int = 42, test_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, ColumnTransformer, pd.DataFrame, pd.DataFrame, list]:
    """_summary_

    Args:
        dataset (pd.DataFrame): DataFrame original de pandas.
        resultado_eda (dict): Diccionario con el resultado del EDA.
        random_state (int, optional): Semilla aleatoria para reproducibilidad. Defaults to 42.
        test_size (float, optional): Proporción del dataset para test (0.0 a 1.0). Defaults to 0.2.

    Raises:
        ValueError: Si la columna target no existe en el dataset.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, ColumnTransformer, pd.DataFrame, pd.DataFrame, list]:
            X_train (preprocesado), X_test (preprocesado), y_train, y_test, preprocesador, X_train_raw, X_test_raw, columnas_a_eliminar.
    """
    from sklearn.model_selection import train_test_split

    problema_tipo = resultado_eda.get("problem_type", "classification").lower()
    columna_target = resultado_eda["target_column"]
    analisis_columnas = resultado_eda.get("column_analysis", {})
    preprocesado_recomendado = resultado_eda.get("recommended_preprocessing", [])
    estrategia_nulos = resultado_eda.get("missing_values_strategy", {})

    # Validar que la columna target existe en el dataset
    if columna_target not in dataset.columns:
        raise ValueError(
            f"La columna target '{columna_target}' no existe en el dataset. "
            f"Columnas disponibles: {list(dataset.columns)}"
        )

    CloudWatchLogger.get().info(f"[Preprocess] Iniciando preprocesado. Target: {columna_target}, Tipo problema: {problema_tipo}")
    CloudWatchLogger.get().info(f"[Preprocess] Preprocesado recomendado: {preprocesado_recomendado}")

    # Separar X e y
    y = dataset[columna_target].copy()
    X = dataset.drop(columns=[columna_target])

    # Eliminar filas con NaN en el target si existe
    nulos_y = y.isna().sum()
    if nulos_y > 0:
        estrategia_target = estrategia_nulos.get(columna_target, "")
        if estrategia_target in ("impute_mean", "impute_median"):
            valor_imputacion = y.mean() if estrategia_target == "impute_mean" else y.median()
            y = y.fillna(valor_imputacion)
            CloudWatchLogger.get().info(f"[Preprocess] Target '{columna_target}': {nulos_y} NaN imputados con {estrategia_target} ({valor_imputacion:.4f}).")
        elif estrategia_target == "impute_mode":
            valor_imputacion = y.mode()[0] if not y.mode().empty else y.dropna().iloc[0]
            y = y.fillna(valor_imputacion)
            CloudWatchLogger.get().info(f"[Preprocess] Target '{columna_target}': {nulos_y} NaN imputados con mode ({valor_imputacion}).")
        else:
            # Default según tipo de problema
            if problema_tipo == "regression":
                valor_imputacion = y.median()
                y = y.fillna(valor_imputacion)
                CloudWatchLogger.get().info(f"[Preprocess] Target '{columna_target}': {nulos_y} NaN imputados con median (default) ({valor_imputacion:.4f}).")
            else:
                valor_imputacion = y.mode()[0] if not y.mode().empty else y.dropna().iloc[0]
                y = y.fillna(valor_imputacion)
                CloudWatchLogger.get().info(f"[Preprocess] Target '{columna_target}': {nulos_y} NaN imputados con mode (default) ({valor_imputacion}).")

    # Identificar columnas por tipo
    columnas_numericas = []
    columnas_categoricas = []
    columnas_a_eliminar = []

    for col in X.columns:
        info = analisis_columnas.get(col, {})
        tipo = info.get("type", "numeric")
        rol = info.get("role", "feature")

        if tipo in ("numeric", "datetime"):
            columnas_numericas.append(col)
        elif tipo in ("categorical", "text"):
            columnas_categoricas.append(col)
        else:
            # Tipo desconocido - intentar inferir del dtype de pandas
            if pd.api.types.is_numeric_dtype(X[col]):
                columnas_numericas.append(col)
            else:
                columnas_categoricas.append(col)

    # Identificar columnas para eliminar según missing_values_strategy
    for col, estrategia in estrategia_nulos.items():
        if estrategia == "drop_column" and col in X.columns:
            columnas_a_eliminar.append(col)

    # También eliminar columnas con rol "id"
    for col, info in analisis_columnas.items():
        if info.get("role") == "id" and col in X.columns and col not in columnas_a_eliminar:
            columnas_a_eliminar.append(col)

    # Aplicar eliminación de columnas
    if columnas_a_eliminar:
        CloudWatchLogger.get().info(f"[Preprocess] Eliminando columnas: {columnas_a_eliminar}")
        X = X.drop(columns=[c for c in columnas_a_eliminar if c in X.columns])
        # Refiltrar listas de columnas
        columnas_numericas = [c for c in columnas_numericas if c in X.columns]
        columnas_categoricas = [c for c in columnas_categoricas if c in X.columns]

    CloudWatchLogger.get().info(
        f"[Preprocess] Columnas tras limpieza: {len(columnas_numericas)} numéricas, {len(columnas_categoricas)} categóricas",
    )

    # Forzar conversion de columnas numéricas a tipo numérico
    X, columnas_numericas, columnas_categoricas = convertir_columnas_a_numericas(
        X, columnas_numericas, columnas_categoricas
    )

    # Construir ColumnTransformer
    transformadores = []

    if columnas_numericas:
        pasos_numericos = []

        # Imputación para numéricas
        if "impute_mean" in preprocesado_recomendado:
            pasos_numericos.append(("num_imputer", SimpleImputer(strategy="mean")))
        elif "impute_median" in preprocesado_recomendado:
            pasos_numericos.append(("num_imputer", SimpleImputer(strategy="median")))

        # Escalado
        if "standard_scaler" in preprocesado_recomendado:
            pasos_numericos.append(("num_scaler", StandardScaler()))

        if pasos_numericos:
            pipeline_numerico = Pipeline(pasos_numericos, memory=None)
            transformadores.append(("num", pipeline_numerico, columnas_numericas))
        else:
            # Sin transformaciones explícitas, pasar tal cual
            transformadores.append(("num", "passthrough", columnas_numericas))
    else:
        CloudWatchLogger.get().info("[Preprocess] Sin columnas numéricas para transformar.")

    if columnas_categoricas:
        pasos_categoricos = []

        # Imputación para categóricas
        if "impute_mode" in preprocesado_recomendado:
            pasos_categoricos.append(("cat_imputer", SimpleImputer(strategy="most_frequent")))

        # One-hot encoding
        if "one_hot_encode" in preprocesado_recomendado:
            pasos_categoricos.append(
                ("cat_encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
            )

        if pasos_categoricos:
            pipeline_categorico = Pipeline(pasos_categoricos, memory=None)
            transformadores.append(("cat", pipeline_categorico, columnas_categoricas))
        else:
            transformadores.append(("cat", "passthrough", columnas_categoricas))
    else:
        CloudWatchLogger.get().info("[Preprocess] Sin columnas categóricas para transformar.")

    preprocesador = ColumnTransformer(
        transformadores,
        remainder="drop",  # Eliminar columnas no especificadas explícitamente
        verbose_feature_names_out=False,
    )

    CloudWatchLogger.get().info(f"[Preprocess] ColumnTransformer construido con {len(transformadores)} transformadores.")

    # Division train/test
    estratificar = None
    if problema_tipo == "classification":
        try:
            conteos = y.value_counts()
            if (conteos >= 2).all():
                estratificar = y
                CloudWatchLogger.get().info("[Preprocess] Estratificación activada para clasificación.")
        except Exception:
            CloudWatchLogger.get().warning("[Preprocess] No se pudo aplicar estratificación; usando split simple.")

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state,
        stratify=estratificar,
    )

    CloudWatchLogger.get().info(
        f"[Preprocess] Split completado: train={len(X_train_raw)} muestras, test={len(X_test_raw)} muestras",
    )

    # Ajustar preprocesador y transformar
    try:
        X_train = preprocesador.fit_transform(X_train_raw)
        X_test = preprocesador.transform(X_test_raw)

        # Convertir a DataFrame para mantener nombres de columnas si es posible
        try:
            nombres_features = preprocesador.get_feature_names_out()
            X_train = pd.DataFrame(X_train, columns=nombres_features)
            X_test = pd.DataFrame(X_test, columns=nombres_features)
        except Exception:
            CloudWatchLogger.get().warning("[Preprocess] No se pudieron obtener nombres de features; usando arrays.")
    except Exception as error:
        CloudWatchLogger.get().error(f"[Preprocess] Error al aplicar preprocesador: {error}")
        raise

    CloudWatchLogger.get().info(
        f"[Preprocess] Preprocesado completado. X_train: {X_train.shape}, X_test: {X_test.shape}",
    )

    return X_train, X_test, y_train, y_test, preprocesador, X_train_raw, X_test_raw, columnas_a_eliminar, columnas_numericas, columnas_categoricas


def convertir_columnas_a_numericas(X: pd.DataFrame, columnas_numericas: list, columnas_categoricas: list, date_formats: dict = None) -> Tuple[pd.DataFrame, list, list]:
    """
    Fuerza la conversión de columnas marcadas como numéricas/datetime a tipo numérico.
    Si el LLM proporcionó un formato de fecha específico, lo usa para parsear la columna.
    Si no es convertible, intenta interpretarla como datetime con inferencia automática.
    Si tampoco es datetime, la mueve a categóricas.

    Args:
        X (pd.DataFrame): DataFrame con las features.
        columnas_numericas (list): Lista de columnas marcadas como numéricas.
        columnas_categoricas (list): Lista de columnas marcadas como categóricas.
        date_formats (dict, optional): Mapa columna -> formato strftime sugerido por el LLM.

    Returns:
        Tuple[pd.DataFrame, list, list]: DataFrame convertido, lista numéricas actualizada, lista categóricas actualizada.
    """
    for col in list(columnas_numericas):
        if pd.api.types.is_numeric_dtype(X[col]):
            continue

        # Intentar formato específico del LLM
        if date_formats and col in date_formats:
            fmt = date_formats[col]
            try:
                dt = pd.to_datetime(X[col], format=fmt, errors='coerce')
                if dt.notna().sum() > len(X) * 0.5:
                    X[col] = dt.astype('int64') // 10**9
                    CloudWatchLogger.get().info(f"[Preprocess] Columna '{col}' convertida con formato '{fmt}' (timestamp numérico).")
                    continue
                else:
                    CloudWatchLogger.get().warning(f"[Preprocess] Formato '{fmt}' para '{col}' parseó menos del 50% de valores. Intentando inferencia...")
            except Exception as error:
                CloudWatchLogger.get().warning(f"[Preprocess] Formato '{fmt}' falló para '{col}': {error}. Intentando inferencia...")

        # Fallback: pd.to_numeric
        converted = pd.to_numeric(X[col], errors='coerce')
        nulos_nuevos = converted.isna().sum() - X[col].isna().sum()

        # Si mas del 50% no-numericos, intentar datetime con inferencia
        if nulos_nuevos > len(X) * 0.5:
            try:
                dt = pd.to_datetime(X[col], errors='coerce')
                if dt.notna().sum() > len(X) * 0.5:
                    X[col] = dt.astype('int64') // 10**9
                    CloudWatchLogger.get().info(f"[Preprocess] Columna '{col}' convertida de datetime a timestamp numérico (inferencia automática).")
                    continue
            except Exception:
                pass
            # No es datetime convertible: mover a categóricas
            columnas_numericas.remove(col)
            if col not in columnas_categoricas:
                columnas_categoricas.append(col)
            CloudWatchLogger.get().warning(f"[Preprocess] Columna '{col}' movida a categóricas (no convertible a numérico).")
        else:
            X[col] = converted
            CloudWatchLogger.get().info(f"[Preprocess] Columna '{col}' convertida a numérico ({nulos_nuevos} valores no-numéricos -> NaN).")
    return X, columnas_numericas, columnas_categoricas
