#######################
#       Imports       #
#######################
import sys
sys.path.insert(0, "/opt/training-server")
from common.logger import CloudWatchLogger
import os
from pathlib import Path
from typing import Optional
import boto3
from botocore.exceptions import ClientError


###########################
#        Functions        #
###########################
def descargar_dataset(bucket: str, clave: str, ruta_local: str, cliente_s3: Optional[object] = None) -> str:
    """
    Descarga un archivo desde S3 a una ruta local.
    Args:
        bucket (str): Nombre del bucket S3.
        clave (str): Clave del objeto (ruta dentro del bucket).
        ruta_local (str): Ruta de destino en el sistema de archivos local.
        cliente_s3 (Optional[object], optional): Cliente boto3 S3 opcional. Defaults to None.

    Raises:
        FileNotFoundError: Si el objeto no existe en S3 o si el archivo no se encuentra tras la descarga.
        FileNotFoundError: Si el archivo local no existe tras la descarga.

    Returns:
        str: Ruta absoluta del archivo descargado.
    """
    if cliente_s3 is None:
        cliente_s3 = boto3.client("s3", region_name="eu-west-1")

    # Asegurar que el directorio de destino existe
    directorio_destino = os.path.dirname(ruta_local)
    if directorio_destino:
        Path(directorio_destino).mkdir(parents=True, exist_ok=True)

    CloudWatchLogger.get().info(f"[S3] Descargando s3://{bucket}/{clave} -> {ruta_local}")

    try:
        cliente_s3.download_file(bucket, clave, ruta_local)
    except ClientError as error:
        codigo = error.response["Error"]["Code"]
        if codigo == "404":
            raise FileNotFoundError(
                f"El objeto s3://{bucket}/{clave} no existe en S3."
            ) from error
        CloudWatchLogger.get().error(f"[S3] Error al descargar {clave}: {error}")
        raise

    # Verificar que el archivo se descargó correctamente
    if not os.path.isfile(ruta_local):
        raise FileNotFoundError(
            f"El archivo no se encontró tras la descarga: {ruta_local}"
        )

    CloudWatchLogger.get().info(f"[S3] Descarga completada: {ruta_local} ({os.path.getsize(ruta_local) / 1024:.2f} KB)")
    return os.path.abspath(ruta_local)


def subir_artefacto(ruta_local: str, bucket: str, clave: str, cliente_s3: Optional[object] = None) -> str:
    """
    Sube un archivo local a S3.
    Args:
        ruta_local (str): Ruta del archivo a subir.
        bucket (str): Nombre del bucket S3 de destino.
        clave (str): Clave del objeto en S3.
        cliente_s3 (Optional[object], optional): Cliente boto3 S3 opcional. Defaults to None.

    Raises:
        FileNotFoundError: Si el archivo local no existe o si falla la subida a S3.

    Returns:
        str: URI S3 del objeto subido.
    """
    if not os.path.isfile(ruta_local):
        raise FileNotFoundError(f"Archivo local no encontrado: {ruta_local}")

    if cliente_s3 is None:
        cliente_s3 = boto3.client("s3", region_name="eu-west-1")

    CloudWatchLogger.get().info(f"[S3] Subiendo {ruta_local} -> s3://{bucket}/{clave}")

    try:
        cliente_s3.upload_file(ruta_local, bucket, clave)
    except ClientError as error:
        CloudWatchLogger.get().error(f"[S3] Error al subir {clave}: {error}")
        raise

    uri_s3 = f"s3://{bucket}/{clave}"
    CloudWatchLogger.get().info(f"[S3] Subida completada: {uri_s3}")
    return uri_s3
