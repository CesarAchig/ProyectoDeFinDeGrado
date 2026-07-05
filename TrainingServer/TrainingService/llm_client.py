#######################
#       Imports       #
#######################
import json
from common.logger import CloudWatchLogger
import re
import time
from typing import Optional
from openai import OpenAI


#################
#    Classes    #
#################
class OpenCodeClient:
    """
    Cliente para la API de OpenCode (compatible con OpenAI).

    Proporciona reintentos con backoff exponencial y extracción segura de JSON desde respuestas markdown.

    Attributes:
        modelo (str): Identificador del modelo a usar.
        max_reintentos (int): Número máximo de reintentos ante fallos transitorios.
        cliente (OpenAI): Instancia del cliente de OpenAI configurada.
    """


    ###########################
    #        Functions        #
    ###########################
    def __init__(self, api_key: str, modelo: str = "glm-5.1", url_base: str = "https://opencode.ai/zen/go/v1", max_reintentos: int = 3) -> None:
        """
        Inicializa el cliente de OpenCode.
        Args:
            api_key (str): Clave de API para autenticación.
            modelo (str, optional): Identificador del modelo a usar. Defaults to "glm-5.1".
            url_base (_type_, optional): URL base de la API. Defaults to "https://opencode.ai/zen/go/v1".
            max_reintentos (int, optional): Número máximo de reintentos ante fallos transitorios. Defaults to 3.
        """
        self.modelo = modelo
        self.max_reintentos = max_reintentos
        self.cliente = OpenAI(api_key=api_key, base_url=url_base)
        CloudWatchLogger.get().info(f"[LLM] Cliente OpenCode inicializado: modelo={modelo}, url={url_base}")


    def chat(self, prompt_sistema: str, prompt_usuario: str, temperatura: float = 0.7, max_tokens: int = 10000) -> str:
        """
        Envía una consulta al modelo LLM con reintentos automáticos.
        Args:
            prompt_sistema (str): Mensaje de sistema (instrucciones para el LLM).
            prompt_usuario (str): Mensaje de usuario (datos/consulta).
            temperatura (float, optional): Nivel de creatividad (0.0 = determinista, 1.0 = creativo). Defaults to 0.7.
            max_tokens (int, optional): Máximo de tokens en la respuesta. Defaults to 10000.

        Raises:
            RuntimeError: Si se agotan los reintentos sin éxito.

        Returns:
            str: Texto de respuesta del modelo.
        """
        mensajes = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario},
        ]

        ultimo_error = None

        for intento in range(1, self.max_reintentos + 1):
            try:
                CloudWatchLogger.get().info(
                    f"[LLM] Llamada (intento {intento}/{self.max_reintentos}): model={self.modelo}, temp={temperatura:.2f}, max_tokens={max_tokens}",
                )

                respuesta = self.cliente.chat.completions.create(
                    model=self.modelo,
                    messages=mensajes,
                    temperature=temperatura,
                    max_tokens=max_tokens,
                )

                contenido = respuesta.choices[0].message.content
                CloudWatchLogger.get().debug(f"[LLM] Respuesta recibida: {len(contenido)} caracteres")
                return contenido

            except Exception as error:
                ultimo_error = error
                mensaje_error = str(error).lower()

                # Determinar si es un error transitorio (rate limit, timeout)
                es_transitorio = any(
                    palabra in mensaje_error
                    for palabra in ["rate limit", "timeout", "connection", "429", "503", "502"]
                )

                if intento < self.max_reintentos and es_transitorio:
                    espera = 2 ** intento  # Backoff exponencial: 2, 4, 8 segundos
                    CloudWatchLogger.get().warning(
                        f"[LLM] Error transitorio (intento {intento}/{self.max_reintentos}): {error}. Reintentando en {espera}s...",
                    )
                    time.sleep(espera)
                else:
                    CloudWatchLogger.get().error(
                        f"[LLM] Error definitivo tras {intento} intentos: {error}",
                    )
                    break

        raise RuntimeError(
            f"Fallo en comunicación con LLM tras {self.max_reintentos} intentos. "
            f"Último error: {ultimo_error}"
        )


    @staticmethod
    def extraer_json(respuesta: str) -> Optional[dict]:
        """
        Extrae un objeto JSON de una respuesta que puede contener
        bloques markdown ```json ... ``` o texto plano.
        Args:
            respuesta (str): Texto de respuesta del LLM.

        Returns:
            Optional[dict]: Objeto JSON extraído, o None si falla el parseo.
        """
        # Intentar extraer de bloque markdown ```json ... ```
        patron_markdown = r"```(?:json)?\s*\n?(.*?)\n?```"
        coincidencias = re.findall(patron_markdown, respuesta, re.DOTALL)

        candidatos_json = coincidencias if coincidencias else [respuesta]

        for candidato in candidatos_json:
            candidato = candidato.strip()
            try:
                return json.loads(candidato)
            except json.JSONDecodeError:
                continue

        try:
            inicio = respuesta.index("{")
            fin = respuesta.rindex("}") + 1
            return json.loads(respuesta[inicio:fin])
        except (ValueError, json.JSONDecodeError):
            pass

        CloudWatchLogger.get().error("[LLM] No se pudo extraer JSON válido de la respuesta del LLM.")
        return None
