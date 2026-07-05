import json
import os
import boto3

# Inicialización fuera del handler para aprovechar warm starts
dynamodb = boto3.resource('dynamodb')
_table_name = os.environ.get('USERS_TABLE_NAME', 'users-auth-table')
table = dynamodb.Table(_table_name)

def lambda_handler(event, context):
    """
    Autentica a un usuario buscándolo en DynamoDB.
    Espera: queryStringParameters.userName
    Devuelve: 200 + {message, token, username} en caso de éxito
              400 si falta userName
              401 si no se encuentra el usuario
              500 en errores inesperados
    """
    print(f"[Authentication] Inicio de ejecución. Event: {json.dumps(event)}")

    query_params = event.get('queryStringParameters') or {}
    username = query_params.get('userName')
    print(f"[Authentication] Parámetro recibido - userName: {username}")

    if not username:
        print("[Authentication] [ERROR] userName es obligatorio pero no fue proporcionado.")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "El parámetro userName es obligatorio"})
        }

    try:
        print(f"[Authentication] Consultando DynamoDB. Tabla: {_table_name}, username: {username}")
        response = table.get_item(Key={'username': username})
        print(f"[Authentication] Respuesta DynamoDB recibida. Item encontrado: {'Item' in response}")

        if 'Item' not in response:
            print(f"[Authentication] Usuario '{username}' no encontrado en DynamoDB. Denegando acceso.")
            return {
                "statusCode": 401,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Credenciales inválidas"})
            }

        user = response['Item']
        print(f"[Authentication] Usuario '{username}' encontrado. Validando api_key...")

        api_key = user.get('api_key', '')
        if not api_key:
            print(f"[Authentication] [ERROR] api_key vacía para usuario '{username}'.")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Error de configuración interna del usuario"})
            }

        print(f"[Authentication] Autenticación exitosa para '{username}'. Devolviendo token.")
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": "Inicio de sesión exitoso",
                "token": api_key,
                "username": username
            })
        }
    except Exception as e:
        print(f"[Authentication] [ERROR] Error inesperado: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Error interno del servidor."})
        }
