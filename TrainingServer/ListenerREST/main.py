#######################
#       Imports       #
#######################
import io
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
import mlflow
from mlflow.exceptions import MlflowException
import pandas as pd
from common.logger import CloudWatchLogger


##########################
#  Global Configuration  #
##########################
LISTENER_PORT: int = int(os.getenv("LISTENER_PORT", "8080"))
DYNAMODB_JOBS_TABLE: str = os.getenv("DYNAMODB_JOBS_TABLE", "training-jobs-table")
TRAINING_PYTHON: str = "/opt/training-server/training-service/venv/bin/python"
TRAINING_SCRIPT: str = "/opt/training-server/training-service/main.py"


#################
#    Classes    #
#################
class TrainingRequest(BaseModel):
    """
    Modelo de datos para la petición de entrenamiento.

    Attributes:
        user (str): El nombre del usuario que solicita el entrenamiento.
        fileName (str): El nombre del archivo o dataset a utilizar.
        targetColumn (Optional[str], optional): El nombre de la columna objetivo. Por defecto es None.
    """
    user: str
    fileName: str
    targetColumn: Optional[str] = None

class PredictionRequest(BaseModel):
    """
    Modelo de datos para la petición de predicción.

    Attributes:
        user (str): El nombre del usuario que solicita la predicción.
        datasetName (str): El nombre del dataset asociado a la predicción.
        features_csv (str): Las características (features) en formato CSV para realizar la predicción.
        mlflowRunId (str): El ID de la ejecución (run) en MLflow que contiene el modelo a utilizar.
    """
    user: str
    datasetName: str
    features_csv: str
    mlflowRunId: str
    

########################
#     Init FastAPI     #
########################
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Configura el logger de CloudWatch al iniciar y finalizar la aplicación.

    Args:
        app (FastAPI): La instancia de la aplicación FastAPI.
    """
    CloudWatchLogger.configure(
        log_group="Training-Server-PFG",
        log_stream="listener-rest"
    )
    yield

app = FastAPI(
    title="ListenerREST", 
    description="Servicio receptor para iniciar entrenamientos de ML en EC2.", 
    version="1.0.0",
    lifespan=lifespan
)


########################
#   Helper Functions   #
########################
def _obtener_cliente_dynamodb():
    """
    Devuelve el recurso Table de DynamoDB usando credenciales IAM de la instancia.

    Returns:
        boto3.resources.factory.dynamodb.Table: Recurso de la tabla DynamoDB para registrar los trabajos (jobs) de entrenamiento.
    """
    recurso = boto3.resource("dynamodb", region_name="eu-west-1")
    return recurso.Table(DYNAMODB_JOBS_TABLE)

def _grabar_estado_inicial(tabla, job_id: str, request: TrainingRequest, timestamp: str) -> None:
    """
    Inserta el registro inicial del trabajo (job) en DynamoDB.

    Args:
        tabla (boto3.resources.factory.dynamodb.Table): Recurso de la tabla DynamoDB.
        job_id (str): El ID único del trabajo de entrenamiento.
        request (TrainingRequest): El objeto con los datos de la solicitud de entrenamiento.
        timestamp (str): La marca de tiempo actual en formato ISO.
    """
    item = {
        "job_id": job_id,
        "user_name": request.user,
        "dataset_name": request.fileName,
        "target_column": request.targetColumn or "",
        "status": "PENDING",
        "created_at": timestamp,
        "updated_at": timestamp,
        "mlflow_run_id": "",
        "error_message": "",
        "algorithm": "",
        "metrics": "",
    }
    tabla.put_item(Item=item)
    CloudWatchLogger.get().info(f"Registro DynamoDB creado para job_id={job_id}")
    CloudWatchLogger.get().info(f"[ListenerREST] Estado inicial registrado en DynamoDB para job_id={job_id}")

def _lanzar_training_service(job_id: str, request: TrainingRequest) -> None:
    """
    Lanza el servicio de entrenamiento (TrainingService) como un subproceso en segundo plano.

    Args:
        job_id (str): El ID único del trabajo de entrenamiento.
        request (TrainingRequest): El objeto con los datos de la solicitud de entrenamiento.
    """
    argumentos = [
        TRAINING_PYTHON,
        TRAINING_SCRIPT,
        "--job-id", job_id,
        "--user", request.user,
        "--dataset", request.fileName,
        "--target", request.targetColumn or "auto",
        "--log-stream", job_id,
    ]
    subprocess.Popen(
        argumentos,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    CloudWatchLogger.get().info(f"TrainingService lanzado para job_id={job_id} con PID desconocido")
    CloudWatchLogger.get().info(f"[ListenerREST] TrainingService lanzado en background para job_id={job_id}")


###############
#  Endpoints  #
###############
@app.post("/start-training")
async def iniciar_entrenamiento(request: TrainingRequest):
    """
    Recibe una solicitud de entrenamiento, registra el trabajo en DynamoDB
    y lanza el TrainingService en segundo plano.

    Args:
        request (TrainingRequest): El objeto con los datos de la solicitud de entrenamiento.

    Returns:
        dict: Un diccionario con el ID del trabajo (job_id), el estado inicial ('started') y un mensaje de confirmación.

    Raises:
        HTTPException: (500) Si ocurre un error al registrar el trabajo en DynamoDB, si no se encuentra el ejecutable, 
                       si hay un error de permisos o si ocurre cualquier otro error inesperado.
    """
    job_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    log = CloudWatchLogger.get()
    log_job = CloudWatchLogger.configure_job("Training-Server-PFG", job_id)
    log_job.info(f"[ListenerREST] Petición recibida: user={request.user} dataset={request.fileName} target={request.targetColumn} job_id={job_id}")

    log.info(f"Petición recibida: user={request.user} dataset={request.fileName} target={request.targetColumn} job_id={job_id}")

    # --- Grabar estado inicial en DynamoDB ---
    try:
        tabla = _obtener_cliente_dynamodb()
        _grabar_estado_inicial(tabla, job_id, request, timestamp)
    except ClientError as error:
        log.error(f"[ListenerREST] Error DynamoDB al grabar job_id={job_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar el entrenamiento en DynamoDB: {error}"
        )
    except Exception as error:
        log.error(f"[ListenerREST] Error inesperado DynamoDB para job_id={job_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado al acceder a DynamoDB: {error}"
        )

    # --- Lanzar TrainingService en background ---
    try:
        _lanzar_training_service(job_id, request)
    except FileNotFoundError as error:
        log.error(f"[ListenerREST] TrainingService no encontrado para job_id={job_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"No se encontró el ejecutable del TrainingService: {error}"
        )
    except PermissionError as error:
        log.error(f"[ListenerREST] Permiso denegado al lanzar TrainingService job_id={job_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Permiso denegado al ejecutar el TrainingService: {error}"
        )
    except Exception as error:
        log.error(f"[ListenerREST] Error al lanzar TrainingService job_id={job_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al iniciar el entrenamiento: {error}"
        )

    log_job.info(f"[ListenerREST] Respuesta 200 enviada al cliente. job_id={job_id}")

    return {
        "job_id": job_id,
        "status": "started",
        "message": "Entrenamiento iniciado correctamente",
    }


@app.get("/health")
async def health_check():
    """
    Endpoint de salud para verificar que el servicio está operativo.

    Returns:
        dict: Un diccionario con el estado general del servicio.
    """
    return {"status": "ok", "service": "listener-rest"}


@app.post("/predict")
async def predict(request: PredictionRequest):
    """
    Recibe una solicitud de predicción, carga el modelo entrenado desde MLflow
    y devuelve las predicciones para las características (features) proporcionadas.

    Args:
        request (PredictionRequest): El objeto de solicitud con el usuario, nombre del dataset, el CSV con las características y el ID de la ejecución en MLflow.

    Returns:
        dict: Un diccionario con la lista de predicciones calculadas.

    Raises:
        HTTPException: (400) Si el CSV de características está vacío o no se puede procesar correctamente.
        HTTPException: (500) Si ocurre un error al conectarse a MLflow, al cargar el modelo o al ejecutar la predicción.
    """
    log = CloudWatchLogger.get()
    log.info(f"[ListenerREST] Recibida petición de predicción para user={request.user} dataset={request.datasetName} mlflowRunId={request.mlflowRunId}")

    # --- Validar que features_csv no está vacío ---
    if not request.features_csv or not request.features_csv.strip():
        log.error(f"[ListenerREST] features_csv vacío para user={request.user} dataset={request.datasetName}")
        raise HTTPException(
            status_code=400,
            detail="El campo 'features_csv' no puede estar vacío."
        )

    # --- Detectar formato CSV (delimitador y separador decimal) ---
    def _detectar_formato_csv(csv_text):
        primera_linea = csv_text.split('\n')[0]
        puntos_y_coma = primera_linea.count(';')
        comas = primera_linea.count(',')
        if puntos_y_coma > comas:
            return ';', ','  # delimitador, decimal
        return ',', '.'      # default

    sep, decimal = _detectar_formato_csv(request.features_csv)
    log.info(f"[ListenerREST] Formato CSV detectado: sep='{sep}', decimal='{decimal}'")

    # --- Parsear features_csv a DataFrame ---
    try:
        df_features = pd.read_csv(
            io.StringIO(request.features_csv),
            sep=sep,
            decimal=decimal,
        )
    except Exception as error:
        log.error(f"[ListenerREST] Error al parsear features_csv: {error}")
        raise HTTPException(
            status_code=400,
            detail=f"Error al parsear 'features_csv' como CSV: {error}"
        )

    # --- Configurar MLflow tracking URI ---
    mlflow_server_ip = os.getenv("MLFLOW_SERVER_IP", "localhost")
    mlflow_tracking_uri = f"http://{mlflow_server_ip}:8080"
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    log.info(f"[ListenerREST] MLflow tracking URI configurado: {mlflow_tracking_uri}")

    # --- Cargar modelo desde MLflow ---
    try:
        modelo = mlflow.sklearn.load_model(f"runs:/{request.mlflowRunId}/model")
    except MlflowException as error:
        log.error(f"[ListenerREST] Error MLflow al cargar modelo run_id={request.mlflowRunId}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al cargar el modelo desde MLflow (run_id={request.mlflowRunId}): {error}"
        )
    except Exception as error:
        log.error(f"[ListenerREST] Error inesperado al cargar modelo run_id={request.mlflowRunId}: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado al cargar el modelo: {error}"
        )

    # --- Detectar y eliminar columna target si está presente en el CSV ---
    try:
        cliente = mlflow.tracking.MlflowClient()
        run = cliente.get_run(request.mlflowRunId)
        target_column = run.data.params.get("target_column", "")
        if target_column and target_column in df_features.columns:
            log.warning(f"[ListenerREST] Columna target '{target_column}' detectada en features_csv. Eliminándola automáticamente.")
            df_features = df_features.drop(columns=[target_column])
    except Exception as error:
        log.warning(f"[ListenerREST] No se pudo verificar la columna target del run {request.mlflowRunId}: {error}")

    # --- Ejecutar predicciones ---
    try:
        predicciones = modelo.predict(df_features)
    except Exception as error:
        log.error(f"[ListenerREST] Error al ejecutar predicciones: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar la predicción: {error}"
        )

    log.info(f"[ListenerREST] Predicciones generadas exitosamente para user={request.user} dataset={request.datasetName}")

    return {"predictions": predicciones.tolist()}
