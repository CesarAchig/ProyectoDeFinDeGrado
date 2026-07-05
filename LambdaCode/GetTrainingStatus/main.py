##########################
#    Import Libraries    #
##########################
import json
import os
import boto3
from boto3.dynamodb.conditions import Key


##########################
#  Global Configuration  #
##########################
_TABLE_NAME = os.environ.get("TRAINING_JOBS_TABLE_NAME", "training-jobs-table")
_DYNAMODB = boto3.resource("dynamodb")
_TABLA = _DYNAMODB.Table(_TABLE_NAME)


###########################
#        Functions        #
###########################
def lambda_handler(event, context):
    """
    Devuelve el estado del trabajo (job) de entrenamiento más reciente para un dataset y usuario dados.

    Args:
        event (dict): El evento desencadenado por API Gateway, que contiene los parámetros 'userName' y 'datasetName' en la query string.
        context (object): El objeto de contexto de ejecución de Lambda.

    Returns:
        dict: Un diccionario con el código de estado HTTP y el cuerpo de la respuesta en formato JSON.
              - 200: Job encontrado, con sus metadatos en el cuerpo.
              - 400: Faltan parámetros obligatorios.
              - 404: No se encontró ningún job para la combinación usuario y dataset.
              - 500: Error interno al consultar DynamoDB.
    """
    print(f"[GetTrainingStatus] Inicio de ejecución. Event: {json.dumps(event)}")

    params = event.get("queryStringParameters") or {}
    user_name = params.get("userName")
    dataset_name = params.get("datasetName")
    print(f"[GetTrainingStatus] Parámetros recibidos - userName: {user_name}, datasetName: {dataset_name}")

    if not user_name or not dataset_name:
        print("[GetTrainingStatus] [ERROR] Parámetros obligatorios faltantes.")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Los parámetros 'userName' y 'datasetName' son obligatorios."
            })
        }

    print(f"[GetTrainingStatus] Conectando a DynamoDB. Tabla: {_TABLE_NAME}")

    try:
        print(f"[GetTrainingStatus] Ejecutando query en GSI 'user-dataset-index' para user='{user_name}', dataset='{dataset_name}'")

        respuesta = _TABLA.query(
            IndexName="user-dataset-index",
            KeyConditionExpression=(
                Key("user_name").eq(user_name) & Key("dataset_name").eq(dataset_name)
            )
        )

        items = respuesta.get("Items", [])
        print(f"[GetTrainingStatus] Query completado. Items encontrados: {len(items)}")

        # --- Si no hay resultados, devolver 404 ---
        if not items:
            print(f"[GetTrainingStatus] No se encontraron jobs para user='{user_name}', dataset='{dataset_name}'")
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": (
                        f"No se encontró ningún job de entrenamiento "
                        f"para el dataset '{dataset_name}' del usuario '{user_name}'."
                    )
                })
            }

        # --- Seleccionar el job más reciente (por created_at) ---
        # Ordenamos descendentemente por created_at y tomamos el primero.
        print(f"[GetTrainingStatus] Ordenando {len(items)} jobs por created_at descendente.")
        job = sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)[0]
        print(f"[GetTrainingStatus] Job seleccionado - job_id: {job.get('job_id')}, status: {job.get('status')}, created_at: {job.get('created_at')}")

        # --- Construir y devolver la respuesta ---
        body = {
            "job_id": job.get("job_id", ""),
            "status": job.get("status", "PENDING"),
            "dataset_name": job.get("dataset_name", ""),
            "target_column": job.get("target_column", ""),
            "algorithm": job.get("algorithm", ""),
            "metrics": job.get("metrics", "{}"),
            "mlflow_run_id": job.get("mlflow_run_id", ""),
            "error_message": job.get("error_message", ""),
            "created_at": job.get("created_at", ""),
            "updated_at": job.get("updated_at", "")
        }
        print(f"[GetTrainingStatus] Respuesta 200 exitosa. Body: {json.dumps(body)}")
        return {
            "statusCode": 200,
            "body": json.dumps(body)
        }

    except Exception as e:
        # --- Error inesperado (conexión, permisos, etc.) ---
        print(f"[GetTrainingStatus] [ERROR] Error inesperado al consultar DynamoDB: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Error interno al consultar DynamoDB."
            })
        }
