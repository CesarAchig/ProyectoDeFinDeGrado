###########################
#   Import Libraries      #
###########################
import logging
import watchtower
import boto3
import os
import sys

###########################
#         Classes         #
###########################
class CloudWatchLogger:
    """
    Logger unificado que envía logs a CloudWatch Logs (boto3) a través de watchtower
    (asíncronamente sin bloquear I/O) y los imprime en stdout.

    Soporta dos modos:
        1. Logger por defecto (Singleton clásico):
           CloudWatchLogger.configure(log_group="Training-Server-PFG", log_stream="listener-rest")
           log = CloudWatchLogger.get()

        2. Logger por job (múltiples loggers):
           log_job = CloudWatchLogger.configure_job(log_group="Training-Server-PFG", log_stream=job_id)
           log_job.info("Mensaje del job")
    """

    
    ##########################
    #  Global Configuration  #
    ##########################
    _loggers: dict = {}          # Dict de loggers por log_stream
    _default_logger = None       # Logger por defecto (retrocompatible)


    ###########################
    #        Functions        #
    ###########################
    @classmethod
    def configure(cls, log_group, log_stream, region_name=None):
        """
        Configura el logger por defecto y lo registra en el diccionario de loggers.
        
        Es compatible con el código existente que asume un logger global.

        Args:
            log_group (str): Nombre del grupo de logs en CloudWatch.
            log_stream (str): Nombre del stream de logs en CloudWatch.
            region_name (str, optional): Nombre de la región de AWS. Por defecto es None.

        Returns:
            logging.Logger: Una instancia de logger configurada.
        """
        logger = cls._create_logger(log_group, log_stream, region_name)
        cls._default_logger = logger
        cls._loggers[log_stream] = logger
        return logger

    @classmethod
    def configure_job(cls, log_group, log_stream, region_name=None):
        """
        Crea un logger independiente para un trabajo (job) específico.
        
        Si ya existe un logger asociado a ese log_stream, se devuelve en lugar de crear uno nuevo.

        Args:
            log_group (str): Nombre del grupo de logs en CloudWatch.
            log_stream (str): Nombre del stream de logs (generalmente el ID del job).
            region_name (str, optional): Nombre de la región de AWS. Por defecto es None.

        Returns:
            logging.Logger: Una instancia de logger configurada para el job específico.
        """
        if log_stream in cls._loggers:
            return cls._loggers[log_stream]
        logger = cls._create_logger(log_group, log_stream, region_name)
        cls._loggers[log_stream] = logger
        return logger

    @classmethod
    def get(cls):
        """
        Devuelve la instancia configurada del logger por defecto.

        Returns:
            logging.Logger: El logger por defecto.

        Raises:
            RuntimeError: Si el logger aún no ha sido configurado llamando a configure().
        """
        if cls._default_logger is None:
            raise RuntimeError(
                "CloudWatchLogger no configurado. "
                "Llama a CloudWatchLogger.configure() primero."
            )
        return cls._default_logger

    @classmethod
    def get_job(cls, log_stream):
        """
        Devuelve el logger configurado para un trabajo (job) específico basado en su log_stream.

        Args:
            log_stream (str): El nombre del stream de logs asignado al job.

        Returns:
            logging.Logger: El logger asociado al job específico.

        Raises:
            RuntimeError: Si no se ha configurado un logger para el log_stream especificado.
        """
        if log_stream not in cls._loggers:
            raise RuntimeError(
                f"No hay logger configurado para log_stream={log_stream}. "
                f"Llama a CloudWatchLogger.configure_job() primero."
            )
        return cls._loggers[log_stream]

    # --------------------------------------------------
    #  Método privado de creación
    # --------------------------------------------------
    @classmethod
    def _create_logger(cls, log_group, log_stream, region_name=None):
        """
        Crea y configura un logger con handlers de stdout y CloudWatch.

        Args:
            log_group (str): Nombre del grupo de logs en CloudWatch.
            log_stream (str): Nombre del stream de logs en CloudWatch.
            region_name (str, optional): Nombre de la región de AWS. Por defecto es None.

        Returns:
            logging.Logger: Una instancia de logger configurada.
        """
        region = region_name or os.environ.get('AWS_REGION', 'eu-west-1')
        boto3_client = boto3.client("logs", region_name=region)

        # Usar la librería de logging nativa de python
        logger = logging.getLogger(f"{log_group}_{log_stream}")
        logger.setLevel(logging.DEBUG)
        # Evitar logs duplicados
        logger.propagate = False

        # Formato estándar de los logs
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')

        # Handler 1: Console / stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Handler 2: CloudWatch via watchtower
        try:
            cw_handler = watchtower.CloudWatchLogHandler(
                log_group_name=log_group,
                log_stream_name=log_stream,
                boto3_client=boto3_client,
                create_log_group=True,
                create_log_stream=True,
                send_interval=20,      # Enviar lotes cada 20 segundos
                max_batch_count=1000,  # O si se acumulan 1000 logs
            )
            cw_handler.setFormatter(formatter)
            logger.addHandler(cw_handler)
        except Exception as e:
            print(f"[ERROR] [CloudWatchLogger] Falló al configurar watchtower: {str(e)}", file=sys.stderr)

        return logger
