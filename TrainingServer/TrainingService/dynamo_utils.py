#######################
#       Imports       #
#######################
from common.logger import CloudWatchLogger
from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import ClientError


###########################
#        Functions        #
###########################
def actualizar_estado_job(nombre_tabla: str, job_id: str, estado: str, **campos_extra: Any) -> None:
    """
    Actualiza parcialmente un registro de job en DynamoDB.
    Construye dinámicamente la expresión de actualización.
    Args:
        nombre_tabla (str): Nombre de la tabla DynamoDB.
        job_id (str): Identificador único del job.
        estado (str): Nuevo estado (RUNNING, COMPLETED, FAILED).
        **campos_extra(Any): Campos adicionales a actualizar (ej: error_message, algorithm, metrics, mlflow_run_id).
    """
    recurso = boto3.resource("dynamodb", region_name="eu-west-1")
    tabla = recurso.Table(nombre_tabla)

    # Construir expresiones de actualización dinámicamente
    expresiones_set = ["#st = :st"]
    nombres_atributo = {"#st": "status"}
    valores_atributo = {":st": estado}

    # Siempre actualizar el timestamp
    expresiones_set.append("#up = :up")
    nombres_atributo["#up"] = "updated_at"
    from datetime import datetime, timezone
    valores_atributo[":up"] = datetime.now(timezone.utc).isoformat()

    for nombre_campo, valor in campos_extra.items():
        # Sanitizar nombre de campo para evitar conflictos con palabras reservadas
        clave_placeholder = f"#{nombre_campo}"
        valor_placeholder = f":{nombre_campo}v"
        nombres_atributo[clave_placeholder] = nombre_campo
        valores_atributo[valor_placeholder] = str(valor) if not isinstance(valor, (str, int, float)) else valor
        expresiones_set.append(f"{clave_placeholder} = {valor_placeholder}")

    expresion_actualizacion = "SET " + ", ".join(expresiones_set)

    CloudWatchLogger.get().info(
        f"[DynamoDB] Actualizando job_id={job_id}, status={estado}, extra={list(campos_extra.keys())}",
    )

    try:
        tabla.update_item(
            Key={"job_id": job_id},
            UpdateExpression=expresion_actualizacion,
            ExpressionAttributeNames=nombres_atributo,
            ExpressionAttributeValues=valores_atributo,
        )
        CloudWatchLogger.get().info(f"[DynamoDB] Actualizado correctamente para job_id={job_id}")
    except ClientError as error:
        CloudWatchLogger.get().error(f"[DynamoDB] Error al actualizar job_id={job_id}: {error}")
        raise


def obtener_job(nombre_tabla: str, job_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene un registro completo de job desde DynamoDB.
    Args:
        nombre_tabla (str): Nombre de la tabla DynamoDB.
        job_id (str): Identificador único del job.

    Returns:
        Optional[Dict[str, Any]]: Diccionario con los datos del job, o None si no existe.
    """
    recurso = boto3.resource("dynamodb", region_name="eu-west-1")
    tabla = recurso.Table(nombre_tabla)

    CloudWatchLogger.get().debug(f"[DynamoDB] Consultando job_id={job_id}")

    try:
        respuesta = tabla.get_item(Key={"job_id": job_id})
        item = respuesta.get("Item")
        if item:
            CloudWatchLogger.get().debug(f"[DynamoDB] Job encontrado: {job_id}")
        else:
            CloudWatchLogger.get().warning(f"[DynamoDB] Job no encontrado: {job_id}")
        return item
    except ClientError as error:
        CloudWatchLogger.get().error(f"[DynamoDB] Error al consultar job_id={job_id}: {error}")
        raise
