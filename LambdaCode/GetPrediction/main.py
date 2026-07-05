##########################
#    Import Libraries    #
##########################
import json
import os
import base64
import socket
import urllib.request
import urllib.error
import boto3
from boto3.dynamodb.conditions import Key


##########################
#  Global Configuration  #
##########################
_TABLE_NAME = os.environ.get("TRAINING_JOBS_TABLE_NAME", "training-jobs-table")
_DYNAMODB = boto3.resource("dynamodb", region_name="eu-west-1")
_TABLA = _DYNAMODB.Table(_TABLE_NAME)


###########################
#        Functions        #
###########################
def _post_request(base_url: str, payload: dict):
    """
    Envía una petición POST con datos JSON al Training Server (/predict).

    Args:
        base_url (str): URL base del servidor
        payload (dict): Diccionario con los datos a enviar.

    Returns:
        tuple: Tupla que contiene cuerpo_respuesta_str, codigo_estado.
               En caso de error de red, retorna un error.
    """
    print(f"[GetPrediction] Enviando POST a: {base_url}")
    print(f"[GetPrediction] Payload: {json.dumps(payload)}")

    # Construir el body como JSON codificado en bytes
    post_data = json.dumps(payload).encode('utf-8')

    try:
        # Crear el objeto Request con método POST, body JSON y cabecera Content-Type
        req = urllib.request.Request(base_url, data=post_data)
        req.add_header('Content-Type', 'application/json')

        # Hacer la petición con timeout para no colgar la Lambda
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            print(f"[GetPrediction] Petición exitosa. Código de estado: {status_code}")

            # Leer la respuesta (viene en bytes)
            response_body_bytes = response.read()
            response_body_str = response_body_bytes.decode('utf-8')

            # Intentar mostrar la respuesta como JSON
            try:
                json_response = json.loads(response_body_str)
                print(f"[GetPrediction] Respuesta del servidor (JSON): {json.dumps(json_response)}")
            except json.JSONDecodeError:
                print(f"[GetPrediction] Respuesta del servidor (texto): {response_body_str}")

            return response_body_str, status_code

    except urllib.error.HTTPError as e:
        # El servidor respondió pero con un código de error HTTP (4xx, 5xx)
        print(f"[GetPrediction] [ERROR] Error HTTP: {e.code} {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            print(f"[GetPrediction] [ERROR] Cuerpo del error HTTP: {error_body}")
            return error_body, e.code
        except Exception:
            print("[GetPrediction] [ERROR] No se pudo leer el cuerpo del error HTTP.")
            return str(e.reason), e.code

    except urllib.error.URLError as e:
        # Error a nivel de red: conexión rechazada, DNS, timeout, etc.
        print(f"[GetPrediction] [ERROR] Error de URL (conexión): {e.reason}")

        # Detectar si es un timeout para diferenciar 502 de 504
        if isinstance(e.reason, socket.timeout) or "timed out" in str(e.reason).lower():
            print("[GetPrediction] [ERROR] El Training Server no respondió a tiempo (timeout).")
            return json.dumps({
                "error": "El servidor de entrenamiento no respondió a tiempo.",
                "detalle": str(e.reason)
            }), 504
        else:
            print("[GetPrediction] [ERROR] No se pudo establecer conexión con el Training Server.")
            return json.dumps({
                "error": "No se pudo conectar al servidor de entrenamiento.",
                "detalle": str(e.reason)
            }), 502

    except socket.timeout:
        # Timeout a nivel de socket
        print("[GetPrediction] [ERROR] La petición excedió el tiempo límite (timeout).")
        return json.dumps({
            "error": "El servidor de entrenamiento no respondió a tiempo.",
            "detalle": "Timeout de socket"
        }), 504

    except Exception as e:
        # Cualquier otro error inesperado durante la petición
        print(f"[GetPrediction] [ERROR] Error inesperado durante la petición POST: {e}")
        return json.dumps({
            "error": "Error interno al comunicarse con el servidor de entrenamiento.",
            "detalle": str(e)
        }), 500


###########################
#       Main Logic        #
###########################
def lambda_handler(event, context):
    """
    Manejador principal de la función Lambda para obtener predicciones.

    Recibe una petición desde API Gateway con user, datasetName y features_csv.
    Consulta DynamoDB para obtener el 'mlflow_run_id' del entrenamiento con estado COMPLETED
    más reciente y reenvía la petición al Training Server (/predict).

    Args:
        event (dict): El evento desencadenado por API Gateway, que contiene el body con los datos (user, datasetName, features_csv) codificado en base64.
        context (object): El objeto de contexto de ejecución de Lambda.

    Returns:
        dict: La respuesta HTTP del Training Server, o un mensaje de error con su respectivo código de estado.
    """
    print(f"[GetPrediction] Inicio de ejecución.")

    # Obtener variables de entorno
    ip = os.environ.get("TRAINING_SERVER_IP")
    port = os.environ.get("TRAINING_SERVER_LISTENER_PORT", "8080")
    print(f"[GetPrediction] Variables de entorno - IP: {ip}, Puerto: {port}")

    # Cabeceras comunes para las respuestas
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        # --- Obtener y decodificar el body ---
        body_data = event.get('body')
        if not body_data:
            print("[GetPrediction] [ERROR] El body de la petición está vacío.")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'El body de la petición está vacío.'})
            }

        print("[GetPrediction] Body recibido. Decodificando base64...")

        # El body viene codificado en base64 desde API Gateway
        try:
            decoded_bytes = base64.b64decode(body_data)
            json_string = decoded_bytes.decode('utf-8')
            data = json.loads(json_string)
            print(f"[GetPrediction] Body decodificado correctamente: {json.dumps(data)}")
        except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"[GetPrediction] [ERROR] Error al decodificar el body: {e}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'El body no tiene un formato válido.',
                    'detalle': 'Se esperaba base64 con JSON codificado en UTF-8.'
                })
            }

        # --- Validar campos obligatorios ---
        user = data.get('user')
        if not user:
            print("[GetPrediction] [ERROR] Falta el campo obligatorio 'user'.")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Falta el campo obligatorio "user" en la petición.'
                })
            }

        dataset_name = data.get('datasetName')
        if not dataset_name:
            print("[GetPrediction] [ERROR] Falta el campo obligatorio 'datasetName'.")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Falta el campo obligatorio "datasetName" en la petición.'
                })
            }

        features_csv = data.get('features_csv')
        if not features_csv:
            print("[GetPrediction] [ERROR] Falta el campo obligatorio 'features_csv'.")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Falta el campo obligatorio "features_csv" en la petición.'
                })
            }

        print(f"[GetPrediction] Datos validados. Usuario: {user}, Dataset: {dataset_name}")

        # --- Consultar DynamoDB para obtener el job COMPLETED más reciente ---
        print(f"[GetPrediction] Conectando a DynamoDB. Tabla: {_TABLE_NAME}")
        print(f"[GetPrediction] Ejecutando query en GSI 'user-dataset-index' para user='{user}', dataset='{dataset_name}'")

        respuesta = _TABLA.query(
            IndexName="user-dataset-index",
            KeyConditionExpression=(
                Key("user_name").eq(user) & Key("dataset_name").eq(dataset_name)
            )
        )

        items = respuesta.get("Items", [])
        print(f"[GetPrediction] Query completado. Items encontrados: {len(items)}")

        # --- Filtrar solo jobs COMPLETED ---
        completed_jobs = [item for item in items if item.get("status") == "COMPLETED"]
        print(f"[GetPrediction] Jobs COMPLETED: {len(completed_jobs)}")

        if not completed_jobs:
            print(f"[GetPrediction] [ERROR] No existe un modelo entrenado COMPLETED para user='{user}', dataset='{dataset_name}'")
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': (
                        f"No existe un modelo entrenado para el dataset "
                        f"'{dataset_name}' del usuario '{user}'."
                    )
                })
            }

        # --- Seleccionar el job COMPLETED más reciente (por created_at) ---
        print(f"[GetPrediction] Ordenando {len(completed_jobs)} jobs COMPLETED por created_at descendente.")
        job = sorted(completed_jobs, key=lambda x: x.get("created_at", ""), reverse=True)[0]
        mlflow_run_id = job.get("mlflow_run_id", "")
        print(f"[GetPrediction] Job seleccionado - job_id: {job.get('job_id')}, mlflow_run_id: {mlflow_run_id}")

        if not mlflow_run_id:
            print("[GetPrediction] [ERROR] El job COMPLETED no tiene mlflow_run_id.")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': 'El modelo entrenado no tiene un mlflow_run_id válido.'
                })
            }

        # --- Construir el payload para el Training Server (/predict) ---
        payload = {
            "user": user,
            "datasetName": dataset_name,
            "features_csv": features_csv,
            "mlflowRunId": mlflow_run_id
        }
        print(f"[GetPrediction] Payload construido: {json.dumps(payload)}")

        # --- Enviar petición al Training Server ---
        base_url = f"http://{ip}:{port}/predict"
        print(f"[GetPrediction] Enviando petición a Training Server: {base_url}")
        response_body, status_code = _post_request(base_url, payload)

        # --- Procesar la respuesta del Training Server ---
        if status_code is None:
            print("[GetPrediction] [ERROR] No se recibió código de estado del Training Server.")
            return {
                'statusCode': 502,
                'headers': headers,
                'body': json.dumps({
                    'error': 'No se pudo contactar al servidor de entrenamiento.'
                })
            }

        print(f"[GetPrediction] Respuesta del Training Server - status: {status_code}")

        # Devolver la respuesta del Training Server tal cual al cliente
        return {
            'statusCode': status_code,
            'headers': headers,
            'body': response_body
        }

    except Exception as e:
        print(f"[GetPrediction] [ERROR] Error inesperado en lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Error interno del servidor.'
            })
        }
