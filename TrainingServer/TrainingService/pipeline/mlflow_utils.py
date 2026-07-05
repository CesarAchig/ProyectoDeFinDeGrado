#######################
#       Imports       #
#######################
import os
from pathlib import Path
from typing import Optional
import mlflow
from common.logger import CloudWatchLogger


###########################
#        Functions        #
###########################
def configurar_experimento(uri_mlflow: str, nombre_experimento: str) -> str:
    """
    Configura la URI de tracking, restaura el experimento si está en estado
    'deleted', y lo establece como activo.

    Args:
        uri_mlflow (str): URI del servidor de tracking MLflow.
        nombre_experimento (str): Nombre del experimento.

    Returns:
        str: ID del experimento configurado.
    """
    mlflow.set_tracking_uri(uri_mlflow)
    cliente = mlflow.tracking.MlflowClient()
    experimento = cliente.get_experiment_by_name(nombre_experimento)

    if experimento and experimento.lifecycle_stage == "deleted":
        CloudWatchLogger.get().info(
            f"[MLflow] Experimento '{nombre_experimento}' encontrado en estado deleted. Restaurando..."
        )
        cliente.restore_experiment(experimento.experiment_id)
        CloudWatchLogger.get().info(
            f"[MLflow] Experimento '{nombre_experimento}' restaurado."
        )

    exp = mlflow.set_experiment(nombre_experimento)
    CloudWatchLogger.get().info(
        f"[MLflow] Experimento '{exp.name}' (ID: {exp.experiment_id}) listo."
    )
    return exp.experiment_id


def registrar_codigo_pipeline(directorio_pipeline: str) -> None:
    """
    Registra los scripts .py del directorio pipeline como artefactos de código.

    Args:
        directorio_pipeline (str): Ruta al directorio que contiene los scripts.
    """
    try:
        if os.path.isdir(directorio_pipeline):
            for archivo in Path(directorio_pipeline).glob("*.py"):
                mlflow.log_artifact(str(archivo), artifact_path="code")
            CloudWatchLogger.get().info("[MLflow] Código del pipeline registrado.")
    except Exception as error:
        CloudWatchLogger.get().warning(
            f"[MLflow] No se pudo registrar código del pipeline: {error}"
        )
