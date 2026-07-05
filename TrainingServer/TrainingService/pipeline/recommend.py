#######################
#       Imports       #
#######################
import json
from common.logger import CloudWatchLogger
import os
import time
from typing import Dict


###########################
#        Functions        #
###########################
def recomendar_algoritmo(cliente_llm: object, resultado_eda: dict, max_reintentos: int = 3) -> dict:
    """
    Recomienda el mejor algoritmo de scikit-learn basado en el EDA.
    Args:
        cliente_llm (object): Instancia de OpenCodeClient.
        resultado_eda (dict): Diccionario con el resultado del EDA.
        max_reintentos (int, optional): Número máximo de reintentos para parsear JSON inválido. Defaults to 3.

    Raises:
        ValueError: Si el JSON extraído no contiene los campos necesarios.
        RuntimeError: Si no se logra obtener una recomendación válida.

    Returns:
        dict: Diccionario con la recomendación: algorithm, hyperparameters, rationale.
    """
    # Cargar el prompt del sistema
    prompt_sistema = _cargar_prompt_recommend()

    # Construir el prompt de usuario
    prompt_usuario = _construir_prompt_usuario(resultado_eda)

    CloudWatchLogger.get().info("[Recommend] Iniciando recomendación de algoritmo con LLM.")
    CloudWatchLogger.get().debug(f"[Recommend] Prompt usuario: {len(prompt_usuario)} caracteres")

    ultimo_error = None

    for intento in range(1, max_reintentos + 1):
        try:
            # Llamar al LLM
            respuesta = cliente_llm.chat(
                prompt_sistema=prompt_sistema,
                prompt_usuario=prompt_usuario,
                temperatura=0.3,
                max_tokens=10000,
            )

            # Extraer JSON
            resultado = cliente_llm.extraer_json(respuesta)

            if resultado is None:
                raise ValueError("No se pudo extraer JSON de la respuesta del LLM.")

            # Validar campos obligatorios
            _validar_recomendacion(resultado)

            CloudWatchLogger.get().info(f"[Recommend] Recomendación completada (intento {intento}).")
            CloudWatchLogger.get().info(f"[Recommend] Algoritmo recomendado: {resultado.get('algorithm')}")
            CloudWatchLogger.get().debug(f"[Recommend] Recomendación: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
            return resultado

        except Exception as error:
            ultimo_error = error
            CloudWatchLogger.get().warning(
                f"[Recommend] Intento {intento}/{max_reintentos} fallido: {error}",
            )
            if intento < max_reintentos:
                time.sleep(1.5 ** intento)

    raise RuntimeError(
        f"Recomendación de algoritmo fallida tras {max_reintentos} intentos. "
        f"Último error: {ultimo_error}"
    )


def _cargar_prompt_recommend() -> str:
    """
    Carga el prompt del sistema de recomendación desde archivo
    Raises:
        FileNotFoundError: Si el archivo del prompt no se encuentra en la ruta esperada.

    Returns:
        str: Contenido del prompt de recomendación
    """
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_prompt = os.path.join(directorio_actual, "..", "prompts", "recommend.txt")

    if not os.path.isfile(ruta_prompt):
        raise FileNotFoundError(f"Prompt de recomendación no encontrado: {ruta_prompt}")

    with open(ruta_prompt, "r", encoding="utf-8") as archivo:
        return archivo.read().strip()


def _construir_prompt_usuario(resultado_eda: dict) -> str:
    """
    Construye el prompt de usuario con el resumen del EDA en JSON.
    Args:
        resultado_eda (dict): Diccionario con el resultado del EDA.

    Returns:
        str: Prompt de usuario construido.
    """
    eda_json = json.dumps(resultado_eda, indent=2, ensure_ascii=False)
    return (
        "Based on the following Exploratory Data Analysis (EDA) result, "
        "recommend the best scikit-learn algorithm.\n\n"
        f"```json\n{eda_json}\n```\n\n"
        "Respond ONLY with the JSON object following the schema provided "
        "in the system prompt."
    )


def _validar_recomendacion(resultado: dict) -> None:
    """
    Valida que la recomendación contenga los campos obligatorios.
    Args:
        resultado (dict): Diccionario con la recomendación.

    Raises:
        ValueError: Si falta algún campo obligatorio o si 'hyperparameters' no es un diccionario.
        ValueError: Si 'hyperparameters' no es un diccionario.
    """
    campos_obligatorios = ["algorithm", "hyperparameters"]
    for campo in campos_obligatorios:
        if campo not in resultado:
            raise ValueError(
                f"La recomendación no contiene el campo obligatorio '{campo}'."
            )

    # Validar que hyperparameters sea un diccionario
    if not isinstance(resultado.get("hyperparameters"), dict):
        raise ValueError("El campo 'hyperparameters' debe ser un objeto/diccionario.")
