#######################
#       Imports       #
#######################
import os

from common.logger import CloudWatchLogger
from pydantic_settings import BaseSettings

#################
#    Classes    #
#################
class Config(BaseSettings):
    """
    Configuración de la aplicación cargada desde variables de entorno utilizando Pydantic.

    Attributes:
        opencode_api_key (str): Clave de API para autenticación en OpenCode.
        opencode_model (str): Modelo a utilizar en OpenCode. Por defecto "glm-5.1".
        opencode_base_url (str): URL base de la API de OpenCode.
        mlflow_server_ip (str): Dirección IP del servidor de MLflow.
        mlflow_server_port (int): Puerto del servidor de MLflow. Por defecto 8080.
        dataset_bucket_name (str): Nombre del bucket de S3 para los datasets.
        dynamodb_jobs_table (str): Nombre de la tabla en DynamoDB para registrar los trabajos.
        max_llm_retries (int): Número máximo de reintentos para consultas al LLM. Por defecto 3.
        llm_temperature (float): Temperatura para la generación del LLM. Por defecto 0.7.
        llm_max_tokens (int): Límite máximo de tokens de salida para el LLM. Por defecto 10000.
        train_test_split_ratio (float): Proporción del conjunto de datos utilizada para validación. Por defecto 0.2.
        random_state (int): Semilla aleatoria para la reproducibilidad. Por defecto 42.
    """

    opencode_api_key: str
    opencode_model: str = "glm-5.1"
    opencode_base_url: str = "https://opencode.ai/zen/go/v1"

    mlflow_server_ip: str
    mlflow_server_port: int = 8080

    dataset_bucket_name: str
    dynamodb_jobs_table: str

    # --- Opcionales con valores por defecto ---
    max_llm_retries: int = 3
    llm_temperature: float = 0.7
    llm_max_tokens: int = 10000
    train_test_split_ratio: float = 0.2
    random_state: int = 42

    class Config:
        env_file = ".env"
        extra = "ignore"


###########################
#        Functions        #
###########################
def cargar_configuracion() -> Config:
    """
    Carga la configuración desde variables de entorno y devuelve
    un objeto Config validado automáticamente por Pydantic.
    Returns:
        Config: Instancia de Config con los valores cargados.
    """
    config = Config()

    CloudWatchLogger.get().info("[Config] Configuración cargada correctamente.")
    CloudWatchLogger.get().debug(f"[Config] MLflow URI: http://{config.mlflow_server_ip}:{config.mlflow_server_port}")
    CloudWatchLogger.get().debug(f"[Config] S3 Bucket: {config.dataset_bucket_name}")
    CloudWatchLogger.get().debug(f"[Config] DynamoDB Table: {config.dynamodb_jobs_table}")

    return config
