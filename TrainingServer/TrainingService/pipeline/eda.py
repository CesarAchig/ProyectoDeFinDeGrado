###########################
#         Imports         #
###########################
import json
from common.logger import CloudWatchLogger
import os
import time
from typing import Dict, Optional
import pandas as pd


###########################
#        Functions        #
###########################
def ejecutar_eda(cliente_llm: object, dataset: pd.DataFrame, columna_objetivo_hint: str = "auto", max_reintentos: int = 3) -> dict:
    """
    Realiza el análisis exploratorio de datos (EDA) usando el LLM.

    Args:
        cliente_llm: Instancia de OpenCodeClient.
        dataset: DataFrame de pandas con los datos a analizar.
        columna_objetivo_hint: Nombre de la columna target sugerida, o "auto".
        max_reintentos: Número máximo de reintentos para parsear JSON inválido.

    Returns:
        Diccionario con el resultado del EDA parseado desde JSON.

    Raises:
        RuntimeError: Si no se logra obtener un JSON válido tras los reintentos.
    """
    # Cargo el prompt del sistema
    prompt_sistema = _cargar_prompt_eda()

    # Construyo el prompt de usuario
    prompt_usuario = _construir_prompt_usuario(dataset, columna_objetivo_hint)

    CloudWatchLogger.get().info(f"[EDA] Iniciando EDA con LLM. Columnas: {len(dataset.columns)}, Filas: {len(dataset)}")
    CloudWatchLogger.get().debug(f"[EDA] Prompt usuario: {len(prompt_usuario)} caracteres")

    ultimo_error = None

    for intento in range(1, max_reintentos + 1):
        try:
            # Llamar al LLM
            respuesta = cliente_llm.chat(
                prompt_sistema=prompt_sistema,
                prompt_usuario=prompt_usuario,
                temperatura=0.3,   # Baja temperatura para análisis determinista
                max_tokens=10000,
            )

            # Extraer JSON de la respuesta
            resultado = cliente_llm.extraer_json(respuesta)

            if resultado is None:
                raise ValueError("No se pudo extraer JSON de la respuesta del LLM.")

            # Validar campos obligatorios mínimos
            _validar_resultado_eda(resultado)

            CloudWatchLogger.get().info(f"[EDA] EDA completado exitosamente (intento {intento}).")
            CloudWatchLogger.get().debug(f"[EDA] Resultado EDA: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
            return resultado

        except Exception as error:
            ultimo_error = error
            CloudWatchLogger.get().warning(
                f"[EDA] Intento {intento}/{max_reintentos} fallido: {error}",
            )
            if intento < max_reintentos:
                time.sleep(1.5 ** intento)

    raise RuntimeError(
        f"EDA fallido tras {max_reintentos} intentos. Último error: {ultimo_error}"
    )


def _cargar_prompt_eda() -> str:
    """
    Carga el prompt del sistema EDA desde el archivo prompts/eda.txt.
    Raises:
        FileNotFoundError: Si el archivo no se encuentra.

    Returns:
        str: El contenido del archivo.
    """    
    # Obtener ruta relativa a este archivo
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_prompt = os.path.join(directorio_actual, "..", "prompts", "eda.txt")

    if not os.path.isfile(ruta_prompt):
        raise FileNotFoundError(f"Prompt de EDA no encontrado: {ruta_prompt}")

    with open(ruta_prompt, "r", encoding="utf-8") as archivo:
        return archivo.read().strip()


def _construir_prompt_usuario(dataset: pd.DataFrame, columna_objetivo_hint: str) -> str:
    """
    Construye el prompt de usuario con información del dataset
    Args:
        dataset (pd.DataFrame): DataFrame de pandas con los datos a analizar.
        columna_objetivo_hint (str): Sugerencia para la columna objetivo.

    Returns:
        str: Prompt de usuario construido.
    """
    # Muestra de primeras 30 filas como CSV
    muestra_csv = dataset.head(30).to_csv(index=False)

    # Tipos de columnas inferidos por pandas
    tipos_columnas = []
    for col in dataset.columns:
        dtype = dataset[col].dtype
        nulos = dataset[col].isna().sum()
        tipos_columnas.append(
            f"  - {col}: tipo_pandas={dtype}, valores_nulos={nulos}/{len(dataset)}"
        )

    # Estadísticas adicionales
    num_filas, num_columnas = dataset.shape

    prompt = f"""## Dataset Information
- Number of rows: {num_filas}
- Number of columns: {num_columnas}
- Target column hint: {columna_objetivo_hint}

## Column Types (inferred by pandas)
{chr(10).join(tipos_columnas)}

## Data Sample (first 30 rows as CSV)
```csv
{muestra_csv}
```

Analyze this dataset and respond ONLY with the JSON object following the schema provided in the system prompt.
"""
    return prompt


def _validar_resultado_eda(resultado: dict) -> None:
    """
    Valida que el resultado del EDA contenga los campos mínimos necesarios.

    Args:
        resultado: Diccionario parseado del JSON del LLM.

    Raises:
        ValueError: Si faltan campos obligatorios.
    """
    campos_obligatorios = ["problem_type", "target_column", "column_analysis"]
    for campo in campos_obligatorios:
        if campo not in resultado:
            raise ValueError(
                f"El resultado del EDA no contiene el campo obligatorio '{campo}'."
            )

    # Validar problem_type
    tipo_problema = resultado.get("problem_type", "").lower()
    if tipo_problema not in ("classification", "regression"):
        CloudWatchLogger.get().warning(
            f"[EDA] Tipo de problema inesperado: '{tipo_problema}'. Se intentará continuar."
        )

    # Validar que target_column existe en column_analysis
    columna_target = resultado["target_column"]
    if columna_target not in resultado["column_analysis"]:
        CloudWatchLogger.get().warning(
            f"[EDA] La columna target '{columna_target}' no aparece en column_analysis. "
            "Se añadirá automáticamente."
        )
        resultado["column_analysis"][columna_target] = {
            "type": "numeric",
            "role": "target",
        }

    # Validar date_format
    if "date_format" not in resultado:
        resultado["date_format"] = {}
        CloudWatchLogger.get().info("[EDA] No se encontró date_format en el EDA. Usando inferencia automática para fechas.")
    else:
        num_date_cols = len(resultado["date_format"])
        CloudWatchLogger.get().info(f"[EDA] Formato de fechas detectado para {num_date_cols} columnas: {list(resultado['date_format'].keys())}")
