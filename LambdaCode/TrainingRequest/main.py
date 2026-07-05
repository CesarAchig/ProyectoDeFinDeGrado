##########################
#    Import Libraries    #
##########################
import urllib.request
import urllib.parse
import urllib.error
import json
import base64
import socket
import os


###########################
#        Functions        #
###########################
def post_request(base_url: str, payload: dict):
    """
    Envía una petición POST con datos JSON al Training Server.
    
    Args:
        base_url (str): URL base del servidor (ej. http://IP:puerto).
        payload (dict): Diccionario con los datos a enviar (user, fileName, targetColumn).
    
    Returns:
        tuple: Tupla que contiene (cuerpo_respuesta_str, codigo_estado). 
               En caso de error de red, retorna (mensaje_error, codigo_error).
    """
    print(f"[TrainingRequest] Enviando POST a: {base_url}")
    print(f"[TrainingRequest] Payload: {json.dumps(payload)}")

    post_data = json.dumps(payload).encode('utf-8')

    try:
        req = urllib.request.Request(base_url, data=post_data)
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            print(f"[TrainingRequest] Petición exitosa. Código de estado: {status_code}")

            response_body_bytes = response.read()
            response_body_str = response_body_bytes.decode('utf-8')

            try:
                json_response = json.loads(response_body_str)
                print(f"[TrainingRequest] Respuesta del servidor (JSON): {json.dumps(json_response)}")
            except json.JSONDecodeError:
                print(f"[TrainingRequest] Respuesta del servidor (texto): {response_body_str}")

            return response_body_str, status_code

    except urllib.error.HTTPError as e:
        print(f"[TrainingRequest] [ERROR] Error HTTP: {e.code} {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            print(f"[TrainingRequest] [ERROR] Cuerpo del error HTTP: {error_body}")
            return error_body, e.code
        except Exception:
            print("[TrainingRequest] [ERROR] No se pudo leer el cuerpo del error HTTP.")
            return str(e.reason), e.code

    except urllib.error.URLError as e:
        print(f"[TrainingRequest] [ERROR] Error de URL (conexión): {e.reason}")

        if isinstance(e.reason, socket.timeout) or "timed out" in str(e.reason).lower():
            print("[TrainingRequest] [ERROR] El Training Server no respondió a tiempo (timeout).")
            return json.dumps({
                "error": "El servidor de entrenamiento no respondió a tiempo.",
                "detalle": str(e.reason)
            }), 504
        else:
            print("[TrainingRequest] [ERROR] No se pudo establecer conexión con el Training Server.")
            return json.dumps({
                "error": "No se pudo conectar al servidor de entrenamiento.",
                "detalle": str(e.reason)
            }), 502

    except socket.timeout:
        print("[TrainingRequest] [ERROR] La petición excedió el tiempo límite (timeout).")
        return json.dumps({
            "error": "El servidor de entrenamiento no respondió a tiempo.",
            "detalle": "Timeout de socket"
        }), 504

    except Exception as e:
        print(f"[TrainingRequest] [ERROR] Error inesperado durante la petición POST: {e}")
        return json.dumps({
            "error": "Error interno al comunicarse con el servidor de entrenamiento.",
            "detalle": str(e)
        }), 500


def lambda_handler(event, context):
    """
    Manejador principal de la función Lambda para peticiones de entrenamiento.

    Recibe una petición desde API Gateway, valida los datos,
    construye el payload JSON y lo reenvía al Training Server.

    Args:
        event (dict): El evento desencadenado por API Gateway, que contiene el body con los datos (user, fileName, targetColumn) codificado en base64.
        context (object): El objeto de contexto de ejecución de Lambda.

    Returns:
        dict: Un diccionario con el código de estado HTTP y la respuesta del Training Server en formato JSON.
    """
    print(f"[TrainingRequest] Inicio de ejecución.")

    ip = os.environ.get("TRAINING_SERVER_IP")
    port = os.environ.get("TRAINING_SERVER_LISTENER_PORT", "8080")
    print(f"[TrainingRequest] Variables de entorno - IP: {ip}, Puerto: {port}")

    headers = {
        'Content-Type': 'application/json'
    }

    try:
        body_data = event.get('body')
        if not body_data:
            print("[TrainingRequest] [ERROR] El body de la petición está vacío.")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'El body de la petición está vacío.'})
            }

        print("[TrainingRequest] Body recibido. Decodificando base64...")

        try:
            decoded_bytes = base64.b64decode(body_data)
            json_string = decoded_bytes.decode('utf-8')
            data = json.loads(json_string)
            print(f"[TrainingRequest] Body decodificado correctamente: {json.dumps(data)}")
        except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"[TrainingRequest] [ERROR] Error al decodificar el body: {e}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'El body no tiene un formato válido.',
                    'detalle': 'Se esperaba base64 con JSON codificado en UTF-8.'
                })
            }

        user = data.get('user')
        if not user:
            print("[TrainingRequest] [ERROR] Falta el campo obligatorio 'user'.")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Falta el campo obligatorio "user" en la petición.'
                })
            }

        file_name = data.get('fileName')
        if not file_name:
            print("[TrainingRequest] [ERROR] Falta el campo obligatorio 'fileName'.")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Falta el campo obligatorio "fileName" en la petición.'
                })
            }

        print(f"[TrainingRequest] Datos validados. Usuario: {user}, Archivo: {file_name}")

        payload = {
            "user": user,
            "fileName": file_name,
            "targetColumn": data.get("targetColumn", "")
        }
        print(f"[TrainingRequest] Payload construido: {json.dumps(payload)}")

        base_url = f"http://{ip}:{port}/start-training"
        print(f"[TrainingRequest] Enviando petición a Training Server: {base_url}")
        response_body, status_code = post_request(base_url, payload)
        if status_code is None:
            print("[TrainingRequest] [ERROR] No se recibió código de estado del Training Server.")
            return {
                'statusCode': 502,
                'headers': headers,
                'body': json.dumps({
                    'error': 'No se pudo contactar al servidor de entrenamiento.'
                })
            }

        print(f"[TrainingRequest] Respuesta del Training Server - status: {status_code}")

        job_id = None
        try:
            resp_json = json.loads(response_body)
            job_id = resp_json.get('job_id')
            if job_id:
                print(f"[TrainingRequest] Entrenamiento iniciado. job_id: {job_id}")
        except (json.JSONDecodeError, AttributeError):
            pass

        respuesta_cliente = {
            'message': 'Se ha completado el envío de datos al servidor de entrenamiento.',
            'training_server_response': {
                'status_code': status_code
            }
        }

        if job_id:
            respuesta_cliente['job_id'] = job_id
        else:
            try:
                respuesta_cliente['training_server_response']['body'] = json.loads(response_body)
            except (json.JSONDecodeError, AttributeError):
                respuesta_cliente['training_server_response']['body'] = response_body

        print(f"[TrainingRequest] Respuesta 200 exitosa al cliente.")
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(respuesta_cliente)
        }

    except Exception as e:
        print(f"[TrainingRequest] [ERROR] Error inesperado en lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Error interno del servidor.'
            })
        }
