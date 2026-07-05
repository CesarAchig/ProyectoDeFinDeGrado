##########################
#    Import Libraries    #
##########################
import boto3
import json
import os
import urllib.request
import urllib.error
import urllib.parse
from botocore.exceptions import ClientError


##########################
#  Global Configuration  #
##########################
_S3_CLIENT = boto3.client("s3")
_DYNAMODB = boto3.resource("dynamodb", region_name="eu-west-1")


###########################
#        Functions        #
###########################
def delete_from_s3(dataset_bucket_name, object_key):
  """
  Elimina un objeto específico de un bucket de S3.

  Args:
      dataset_bucket_name (str): El nombre del bucket de S3.
      object_key (str): La clave del objeto (ruta) a eliminar en el bucket.

  Returns:
      dict: Un diccionario con el código de estado HTTP (statusCode) 200 en caso de éxito,
            o un código de error y mensaje si falla.
  """
  print(f"[DeleteData] Verificando existencia en S3. Bucket: {dataset_bucket_name}, Key: {object_key}")

  # Comprobation of object existence
  try:
    _S3_CLIENT.head_object(Bucket=dataset_bucket_name, Key=object_key)
    print(f"[DeleteData] Objeto encontrado en S3. Procediendo a eliminar...")
  except ClientError as e:
    if e.response["Error"]["Code"] == "404":
      print(f"[DeleteData] Objeto no encontrado en S3 (404). Key: {object_key}")
      return {
        "statusCode": 400,
        "body": json.dumps({
          "error": f"Object {object_key} not found in bucket {dataset_bucket_name}"
        })
      }
    else:
      print(f"[DeleteData] [ERROR] Error inesperado de S3: {str(e)}")
      raise

  # Delete object
  _S3_CLIENT.delete_object(Bucket=dataset_bucket_name, Key=object_key)
  print(f"[DeleteData] Objeto eliminado correctamente de S3.")
  return {"statusCode": 200}


def delete_from_dynamodb(user_name: str, dataset_name: str):
  """
  Elimina los registros de DynamoDB asociados a un usuario y dataset.
  
  Utiliza el GSI 'user-dataset-index' para localizar los items.

  Args:
      user_name (str): El nombre del usuario asociado a los registros.
      dataset_name (str): El nombre del dataset asociado a los registros.

  Returns:
      tuple: Una tupla que contiene:
          - bool: True si la operación fue exitosa, False en caso de error.
          - str: Un mensaje detallando el resultado de la operación.
  """
  table_name = os.environ.get("TRAINING_JOBS_TABLE_NAME")
  if not table_name:
    print("[DeleteData] TRAINING_JOBS_TABLE_NAME no está definida. No se pueden eliminar registros de DynamoDB.")
    return False, "TRAINING_JOBS_TABLE_NAME no configurada"

  print(f"[DeleteData] Conectando a DynamoDB. Tabla: {table_name}")
  tabla = _DYNAMODB.Table(table_name)

  try:
    # Consultar el GSI user-dataset-index para obtener los job_ids
    respuesta = tabla.query(
      IndexName="user-dataset-index",
      KeyConditionExpression="user_name = :u AND dataset_name = :d",
      ExpressionAttributeValues={
        ":u": user_name,
        ":d": dataset_name,
      },
      ProjectionExpression="job_id",
    )
    items = respuesta.get("Items", [])
    print(f"[DeleteData] Registros encontrados en DynamoDB: {len(items)}")

    if not items:
      return True, "Sin registros para eliminar en DynamoDB"

    # Eliminar cada item por su job_id (clave primaria)
    eliminados = 0
    for item in items:
      job_id = item.get("job_id", "")
      if not job_id:
        continue
      print(f"[DeleteData] Eliminando registro DynamoDB: job_id={job_id}")
      tabla.delete_item(Key={"job_id": job_id})
      eliminados += 1

    print(f"[DeleteData] {eliminados} registros eliminados de DynamoDB.")
    return True, f"{eliminados} registros eliminados de DynamoDB"

  except ClientError as e:
    mensaje = f"Error al eliminar registros de DynamoDB: {e}"
    print(f"[DeleteData] [ERROR] {mensaje}")
    return False, mensaje


def delete_from_mlflow(user_name: str, dataset_name: str):
  """
  Elimina el experimento de MLflow asociado a un usuario y dataset.
  
  El experimento se identifica por nombre: training-{user_name}-{dataset_name_sin_extension}.

  Args:
      user_name (str): El nombre del usuario propietario del experimento.
      dataset_name (str): El nombre del dataset en el que se basó el experimento.

  Returns:
      tuple: Una tupla que contiene:
          - bool: True si la operación fue exitosa, False en caso de error.
          - str: Un mensaje detallando el resultado de la operación.
  """
  mlflow_ip = os.environ.get("MLFLOW_SERVER_IP")
  if not mlflow_ip:
    print("[DeleteData] MLFLOW_SERVER_IP no está definida. No se pueden eliminar experimentos de MLflow.")
    return False, "MLFLOW_SERVER_IP no configurada"

  base_url = f"http://{mlflow_ip}:8080"
  print(f"[DeleteData] Conectando a MLflow en {base_url}")

  # --- Paso 1: Obtener experimento por nombre ---
  dataset_name_limpio = os.path.splitext(dataset_name)[0]
  experiment_name = f"training-{user_name}-{dataset_name_limpio}"
  print(f"[DeleteData] Buscando experimento: '{experiment_name}'")

  get_by_name_url = f"{base_url}/api/2.0/mlflow/experiments/get-by-name?{urllib.parse.urlencode({'experiment_name': experiment_name})}"

  try:
    req = urllib.request.Request(get_by_name_url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as response:
      data = json.loads(response.read().decode("utf-8"))
    print(f"[DeleteData] Experimento encontrado en MLflow.")
  except urllib.error.HTTPError as e:
    if e.code == 404:
      print(f"[DeleteData] Experimento no encontrado (404). Nada que eliminar.")
      return True, "Experimento no encontrado, nada que eliminar"
    mensaje = f"Error al buscar experimento en MLflow: {e}"
    print(f"[DeleteData] {mensaje}")
    return False, mensaje
  except (urllib.error.URLError, json.JSONDecodeError) as e:
    mensaje = f"Error de conexión al buscar experimento en MLflow: {e}"
    print(f"[DeleteData] {mensaje}")
    return False, mensaje

  experiment_id = data.get("experiment", {}).get("experiment_id", "")
  if not experiment_id:
    print("[DeleteData] No se pudo obtener experiment_id del experimento.")
    return True, "Experimento sin ID, nada que eliminar"

  print(f"[DeleteData] experiment_id={experiment_id}. Procediendo a eliminar...")

  # --- Paso 2: Eliminar experimento ---
  delete_url = f"{base_url}/api/2.0/mlflow/experiments/delete"
  delete_body = json.dumps({"experiment_id": experiment_id}).encode("utf-8")

  try:
    req = urllib.request.Request(delete_url, data=delete_body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10):
      print(f"[DeleteData] Experimento '{experiment_name}' eliminado correctamente.")
      return True, f"Experimento '{experiment_name}' eliminado correctamente"
  except (urllib.error.URLError, urllib.error.HTTPError) as e:
    mensaje = f"Error al eliminar experimento '{experiment_name}': {e}"
    print(f"[DeleteData] {mensaje}")
    return False, mensaje



##########################
#       Main Logic       #
##########################
def lambda_handler(event, context):
  """
  Manejador principal de la función Lambda para eliminar datos.
  
  Elimina los datos asociados a un usuario y dataset específico desde S3, 
  DynamoDB y MLflow basándose en los parámetros proporcionados en la petición.

  Args:
      event (dict): El evento de API Gateway que contiene los parámetros 'userName' y 'datasetName'.
      context (object): El objeto de contexto de ejecución de Lambda.

  Returns:
      dict: La respuesta HTTP que incluye el statusCode y un cuerpo en formato JSON
            indicando el resultado de la operación en los diferentes servicios.
  """
  print(f"[DeleteData] Inicio de ejecución. Event: {json.dumps(event)}")

  try:
    # Get Data From Request (query string parameters)
    params = event.get("queryStringParameters") or {}
    user_name = params.get("userName")
    dataset_name = params.get("datasetName")
    print(f"[DeleteData] Parámetros recibidos - userName: {user_name}, datasetName: {dataset_name}")

    # Validate required parameters
    if not user_name or not dataset_name:
      print("[DeleteData] [ERROR] Faltan parámetros obligatorios.")
      return {
        "statusCode": 400,
        "body": json.dumps({"error": "Faltan los parámetros 'userName' o 'datasetName'"})
      }

    dataset_bucket_name = os.environ.get("DATASET_BUCKET_NAME")
    if not dataset_bucket_name:
      print("[DeleteData] [ERROR] DATASET_BUCKET_NAME no está configurada.")
      return {
        "statusCode": 500,
        "body": json.dumps({"error": "Error interno de configuración del servidor."})
      }

    object_key = f"{user_name}/{dataset_name}"
    print(f"[DeleteData] Key S3 calculada: {object_key}")

    # Delete from S3
    print("[DeleteData] Iniciando eliminación desde S3...")
    result = delete_from_s3(dataset_bucket_name, object_key)
    if result.get("statusCode") >= 400:
      return result

    # Delete from DynamoDB (no interrumpe el flujo si falla)
    print("[DeleteData] Iniciando eliminación desde DynamoDB...")
    exito_ddb, mensaje_ddb = delete_from_dynamodb(user_name, dataset_name)

    # Delete from MlFlow (no interrumpe el flujo si falla)
    print("[DeleteData] Iniciando eliminación desde MLflow...")
    exito_mlflow, mensaje_mlflow = delete_from_mlflow(user_name, dataset_name)

    mensaje_final = f"Dataset '{dataset_name}' eliminado de S3 correctamente."
    if exito_ddb:
      mensaje_final += f" {mensaje_ddb}."
    else:
      mensaje_final += f" Advertencia DynamoDB: {mensaje_ddb}."
      print(f"[DeleteData] ADVERTENCIA DynamoDB: {mensaje_ddb}")

    if exito_mlflow:
      mensaje_final += f" {mensaje_mlflow}."
    else:
      mensaje_final += f" Advertencia MLflow: {mensaje_mlflow}."
      print(f"[DeleteData] ADVERTENCIA MLflow: {mensaje_mlflow}")

    print(f"[DeleteData] Respuesta 200 exitosa. Mensaje: {mensaje_final}")
    return {
      "statusCode": 200,
      "body": json.dumps({
        "message": mensaje_final
      })
    }

  except Exception as e:
    print(f"[DeleteData] [ERROR] Error inesperado: {str(e)}")
    return {
      "statusCode": 500,
      "body": json.dumps({"error": "Error interno del servidor."})
    }
