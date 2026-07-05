import json
import os
import re
import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get('USERS_TABLE_NAME', 'users-auth-table')
_dynamodb = boto3.resource('dynamodb')
_table = _dynamodb.Table(TABLE_NAME)

MAX_TOKEN_LENGTH = 256


def lambda_handler(event, context):
    """
    API Gateway Lambda Authorizer (tipo TOKEN).

    Valida el encabezado 'Authorization: Bearer <token>' contra la base de datos DynamoDB.

    Args:
        event (dict): El evento desencadenado por API Gateway, que contiene el methodArn y el token.
        context (object): El objeto de contexto de ejecución de Lambda.

    Returns:
        dict: Un documento de política de IAM que permite (Allow) o deniega (Deny) el acceso al método.
    """
    print(f"[Authorizer] Inicio de ejecución. methodArn: {event.get('methodArn', '*')}")

    method_arn = event.get('methodArn', '*')
    token = extract_token(event)
    print(f"[Authorizer] Token extraído: {'presente' if token else 'ausente'}")

    if not token:
        print("[Authorizer] Denegando acceso: token no proporcionado o inválido.")
        return generate_policy('anonymous', 'Deny', method_arn)

    try:
        print(f"[Authorizer] Consultando DynamoDB en índice 'api-key-index'.")
        response = _table.query(
            IndexName='api-key-index',
            KeyConditionExpression=Key('api_key').eq(token)
        )

        items = response.get('Items', [])
        print(f"[Authorizer] Query completada. Items encontrados: {len(items)}")

        if not items:
            print("[Authorizer] Token no encontrado en DynamoDB. Denegando acceso.")
            return generate_policy('anonymous', 'Deny', method_arn)

        user = items[0]
        username = str(user.get('username', 'unknown'))
        print(f"[Authorizer] Token válido. Usuario autorizado: {username}")
        return generate_policy(username, 'Allow', method_arn, {
            'username': username
        })
    except Exception as e:
        print(f"[Authorizer] [ERROR] Error inesperado al consultar DynamoDB: {str(e)}")
        return generate_policy('anonymous', 'Deny', method_arn)


def extract_token(event):
    """
    Extrae el token Bearer del campo 'authorizationToken' del evento.

    Args:
        event (dict): El evento desencadenado por API Gateway.

    Returns:
        str or None: El token extraído si existe y tiene una longitud válida, None en caso contrario.
    """
    auth_header = event.get('authorizationToken', '')
    match = re.match(r'^Bearer\s+(.+)$', auth_header, re.IGNORECASE)
    if match:
        token = match.group(1).strip()
        if token and len(token) <= MAX_TOKEN_LENGTH:
            return token
    return None


def generate_policy(principal_id, effect, resource, context=None):
    """
    Genera un documento de política IAM para API Gateway.

    Args:
        principal_id (str): El identificador principal asociado con el token (usualmente el nombre de usuario).
        effect (str): El efecto de la política, típicamente 'Allow' o 'Deny'.
        resource (str): El ARN del recurso de API Gateway (methodArn) al que se aplica la política.
        context (dict, optional): Un diccionario con contexto adicional para pasar a la función Lambda de backend.

    Returns:
        dict: Un diccionario que representa la política IAM y el contexto de autorización.
    """
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }
    if context:
        policy['context'] = context
    return policy
