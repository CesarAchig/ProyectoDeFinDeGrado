#######################
#       Imports       #
#######################
import argparse
import json
import os
import sys
from common.logger import CloudWatchLogger
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd
from config import cargar_configuracion
from s3_utils import descargar_dataset
from llm_client import OpenCodeClient
from dynamo_utils import actualizar_estado_job
from pipeline.eda import ejecutar_eda
from pipeline.recommend import recomendar_algoritmo
from pipeline.preprocess import preprocesar_datos, convertir_columnas_a_numericas
from pipeline.train import entrenar_modelo
from pipeline.plots import generar_graficos
from pipeline.mlflow_utils import configurar_experimento
import mlflow
import mlflow.data
import mlflow.sklearn
from mlflow.models.signature import infer_signature
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer


###########################
#        Functions        #
###########################
def _parsear_argumentos() -> argparse.Namespace:
    """
    Define y parsea los argumentos de línea de comandos.

    Returns:
        argparse.Namespace: Los argumentos de línea de comandos parseados.
    """
    parser = argparse.ArgumentParser(
        description="TrainingService - Motor de entrenamiento automatizado de ML.",
    )
    parser.add_argument(
        "--job-id",
        required=True,
        help="Identificador único del job de entrenamiento.",
    )
    parser.add_argument(
        "--user",
        required=True,
        help="Nombre del usuario propietario del dataset.",
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Nombre del archivo del dataset (clave en S3).",
    )
    parser.add_argument(
        "--target",
        default="auto",
        help="Columna objetivo del dataset. Usa 'auto' para detección automática.",
    )
    parser.add_argument(
        "--log-stream",
        default="default",
        help="Nombre del LogStream en CloudWatch Logs (normalmente el job_id).",
    )
    return parser.parse_args()


def _ejecutar_pipeline(args: argparse.Namespace, config: object) -> int:
    """
    Ejecuta el pipeline completo de entrenamiento.

    Args:
        args: Argumentos de línea de comandos parseados.
        config: Objeto Config con la configuración cargada.

    Returns:
        0 si éxito, 1 si fallo.
    """
    log = CloudWatchLogger.get()
    job_id = args.job_id
    usuario = args.user
    nombre_dataset = args.dataset
    columna_target = args.target

    # Directorio temporal para este job
    directorio_tmp = Path(f"/tmp/training-{job_id}")
    directorio_tmp.mkdir(parents=True, exist_ok=True)
    directorio_graficos = directorio_tmp / "plots"
    directorio_graficos.mkdir(parents=True, exist_ok=True)

    ruta_dataset_local = str(directorio_tmp / nombre_dataset)

    log.info("[TrainingService] " + "=" * 60)
    log.info(f"[TrainingService] Iniciando pipeline para job_id={job_id}")
    log.info(f"[TrainingService]   Usuario: {usuario}")
    log.info(f"[TrainingService]   Dataset: {nombre_dataset}")
    log.info(f"[TrainingService]   Target: {columna_target}")
    log.info(f"[TrainingService]   Directorio temporal: {directorio_tmp}")
    log.info("[TrainingService] " + "=" * 60)


    resultado_eda: Optional[dict] = None
    resultado_recommend: Optional[dict] = None
    modelo: Optional[object] = None
    metricas: Optional[dict] = None
    run_id_mlflow: Optional[str] = None

    uri_mlflow = f"http://{config.mlflow_server_ip}:{config.mlflow_server_port}"
    mlflow.set_tracking_uri(uri_mlflow)
    mlflow.enable_system_metrics_logging()

    nombre_dataset_limpio = os.path.splitext(nombre_dataset)[0]
    nombre_experimento = f"training-{usuario}-{nombre_dataset_limpio}"

    # Configurar experimento de MlFlow
    experiment_id = configurar_experimento(uri_mlflow, nombre_experimento)

    try:
        ############### Fase 1: Actualizar el job en DynamoDB a RUNNING ###############
        log.info("[TrainingService] [Fase 1/8] Actualizando DynamoDB: status=RUNNING")
        actualizar_estado_job(config.dynamodb_jobs_table, job_id, "RUNNING")


        ############### Fase 2: Descargar dataset desde S3 ###############
        log.info("[TrainingService] [Fase 2/8] Descargando dataset desde S3")
        clave_s3 = f"{usuario}/{nombre_dataset}"
        ruta_dataset_local = descargar_dataset(
            bucket=config.dataset_bucket_name,
            clave=clave_s3,
            ruta_local=ruta_dataset_local,
        )
        log.info(f"[TrainingService] Dataset descargado: {ruta_dataset_local}")

        # Cargar dataset en pandas
        with open(ruta_dataset_local, 'r', encoding='utf-8') as f:
            primera_linea = f.readline()
        puntos_y_coma = primera_linea.count(';')
        comas = primera_linea.count(',')
        if puntos_y_coma > comas:
            sep, decimal = ';', ','
        else:
            sep, decimal = ',', '.'
        log.info(f"[TrainingService] Formato CSV detectado: sep='{sep}', decimal='{decimal}'")

        dataset = pd.read_csv(ruta_dataset_local, sep=sep, decimal=decimal)
        log.info(f"[TrainingService] Dataset cargado: {len(dataset)} filas, {len(dataset.columns)} columnas")


        ############### Fase 3: EDA con LLM ###############
        log.info("[TrainingService] [Fase 3/8] Ejecutando EDA con LLM")
        cliente_llm = OpenCodeClient(
            api_key=config.opencode_api_key,
            modelo=config.opencode_model,
            url_base=config.opencode_base_url,
            max_reintentos=config.max_llm_retries,
        )
        resultado_eda = ejecutar_eda(
            cliente_llm=cliente_llm,
            dataset=dataset,
            columna_objetivo_hint=columna_target,
        )
        log.info(f"[TrainingService] EDA completado. Tipo problema: {resultado_eda.get('problem_type')}")
        log.info(f"[TrainingService] Columna target detectada: {resultado_eda.get('target_column')}")

        # Extraer formatos de fecha sugeridos por el LLM
        date_formats = resultado_eda.get("date_format", {})
        if date_formats:
            log.info(f"[TrainingService] Formatos de fecha detectados por LLM: {date_formats}")

        # Actualizar DynamoDB con target_column detectada 
        columna_target_detectada = resultado_eda.get("target_column", "")
        if columna_target_detectada and columna_target in ("auto", ""):
            actualizar_estado_job(
                config.dynamodb_jobs_table,
                job_id,
                "RUNNING",
                target_column=columna_target_detectada,
            )
            log.info(f"[TrainingService] DynamoDB actualizado con target_column detectada: {columna_target_detectada}")


        ############### Fase 4: Recomendación de algoritmo con LLM ###############
        log.info("[TrainingService] [Fase 4/8] Recomendando algoritmo con LLM")
        resultado_recommend = recomendar_algoritmo(
            cliente_llm=cliente_llm,
            resultado_eda=resultado_eda,
        )
        algoritmo = resultado_recommend.get("algorithm", "Desconocido")
        hiperparams = resultado_recommend.get("hyperparameters", {})
        razonamiento = resultado_recommend.get("rationale", "")
        log.info(f"[TrainingService] Algoritmo recomendado: {algoritmo}")
        log.info(f"[TrainingService] Razonamiento: {razonamiento}")


        ############### Fase 5: Preprocesado seguro ###############
        log.info("[TrainingService] [Fase 5/8] Preprocesando datos")
        X_train, X_test, y_train, y_test, preprocesador, X_train_raw, X_test_raw, columnas_a_eliminar, columnas_numericas, columnas_categoricas = preprocesar_datos(
            dataset=dataset,
            resultado_eda=resultado_eda,
            random_state=config.random_state,
            test_size=config.train_test_split_ratio,
        )
        log.info(f"[TrainingService] Preprocesado completado. Train: {X_train.shape}, Test: {X_test.shape}")


        ############### Fases 6-8: Entrenamiento, gráficos y MLflow ###############
        with mlflow.start_run() as run:
            run_id_mlflow = run.info.run_id
            mlflow.sklearn.autolog(
                log_datasets=False,
                log_models=False
            )

            log.info(f"[TrainingService] MLflow run iniciado: {run_id_mlflow}")

            # Tags de la ejecución en MLFlow
            mlflow.set_tag("user_name", usuario)
            mlflow.set_tag("dataset_name", nombre_dataset_limpio)
            mlflow.set_tag("job_id", job_id)

            # Subida de información a MLFlow
            try:
                dataset_mlflow = mlflow.data.from_pandas(
                    df=dataset,
                    name=nombre_dataset,
                    targets=resultado_eda.get("target_column")
                )
                mlflow.log_input(dataset_mlflow, context="training")
                log.info("[TrainingService] Dataset registrado en MLflow (Data Lineage).")
            except Exception as dl_err:
                log.warning(f"[TrainingService] No se pudo registrar dataset nativo: {dl_err}")

            
            try:
                mlflow.log_dict(resultado_eda, "info_ejecucion/eda_result.json")
                mlflow.log_dict(resultado_recommend, "info_ejecucion/recommend_result.json")
                log.info("[TrainingService] Resultados EDA y recomendación logueados a MLflow.")
            except Exception as json_err:
                log.warning(f"[TrainingService] No se pudieron loguear JSONs: {json_err}")

            # Guardado de parámetros en MLFlow``
            tipo_problema = resultado_eda.get("problem_type", "classification")
            params_mlflow = {
                "job_id": job_id,
                "user": usuario,
                "dataset": nombre_dataset,
                "target_column": resultado_eda.get("target_column", ""),
                "target_hint": columna_target,
                "problem_type": tipo_problema,
                "algorithm": algoritmo,
                "rationale": razonamiento,
            }
            # Aplanar hiperparámetros para loguearlos como params individuales
            for k, v in hiperparams.items():
                params_mlflow[f"hyperparameter.{k}"] = v
            try:
                mlflow.log_params(params_mlflow)
                mlflow.log_dict(hiperparams, "info_ejecucion/hyperparameters.json")
            except Exception as param_err:
                log.warning(f"[TrainingService] No se pudieron loguear parámetros: {param_err}")

            # Entrenamiento del modelo con los datos ya limpios 
            log.info("[TrainingService] [Fase 6/8] Entrenando modelo")
            modelo, metricas = entrenar_modelo(
                X_train=X_train,
                y_train=y_train,
                X_test=X_test,
                y_test=y_test,
                nombre_algoritmo=algoritmo,
                hiperparametros=hiperparams,
                tipo_problema=tipo_problema,
            )
            log.info(f"[TrainingService] Entrenamiento completado. Métricas: {metricas}")

            # Métricas manuales (redundancia segura)
            try:
                mlflow.log_metrics(metricas)
            except Exception as met_err:
                log.warning(f"[TrainingService] No se pudieron loguear métricas: {met_err}")

            # Pipeline con Signature + Model Registry
            try:
                def _convert_columns(X, num_cols, cat_cols, date_fmts):
                    X_copy = X.copy()
                    _, num_out, cat_out = convertir_columnas_a_numericas(X_copy, num_cols.copy(), cat_cols.copy(), date_fmts)
                    return X_copy

                def _drop_columns(X, columns_to_drop):
                    return X.drop(columns=columns_to_drop, errors='ignore')

                pipeline_completo = Pipeline([
                    ("converter", FunctionTransformer(_convert_columns, kw_args={'num_cols': columnas_numericas, 'cat_cols': columnas_categoricas, 'date_fmts': date_formats})),
                    ("dropper", FunctionTransformer(_drop_columns, kw_args={'columns_to_drop': columnas_a_eliminar})),
                    ("preprocessor", preprocesador),
                    ("model", modelo)
                ])
                predicciones = pipeline_completo.predict(X_test_raw)
                firma = infer_signature(X_test_raw, predicciones)
                nombre_modelo_registro = f"Modelo_{usuario}_{nombre_dataset_limpio}".replace(" ", "_")
                mlflow.sklearn.log_model(
                    pipeline_completo,
                    artifact_path="model",
                    signature=firma,
                    registered_model_name=nombre_modelo_registro
                )
                log.info(f"[TrainingService] Pipeline registrado en MLflow Model Registry: {nombre_modelo_registro}")
            except Exception as model_err:
                log.error(f"[TrainingService] Error al registrar pipeline en MLflow: {model_err}")
                try:
                    def _convert_columns_fallback(X, num_cols, cat_cols, date_fmts):
                        X_copy = X.copy()
                        _, num_out, cat_out = convertir_columnas_a_numericas(X_copy, num_cols.copy(), cat_cols.copy(), date_fmts)
                        return X_copy

                    def _drop_columns_fallback(X, columns_to_drop):
                        return X.drop(columns=columns_to_drop, errors='ignore')

                    pipeline_completo = Pipeline([
                        ("converter", FunctionTransformer(_convert_columns_fallback, kw_args={'num_cols': columnas_numericas, 'cat_cols': columnas_categoricas, 'date_fmts': date_formats})),
                        ("dropper", FunctionTransformer(_drop_columns_fallback, kw_args={'columns_to_drop': columnas_a_eliminar})),
                        ("preprocessor", preprocesador),
                        ("model", modelo)
                    ])
                    mlflow.sklearn.log_model(pipeline_completo, artifact_path="model")
                    log.info("[TrainingService] Pipeline registrado sin signature.")
                except Exception as fallback_err:
                    log.error(f"[TrainingService] Fallback también falló: {fallback_err}")

            # mlflow.evaluate subida de métricas y gráficos automáticos 
            try:
                eval_data = X_test_raw.copy()
                eval_data[resultado_eda.get("target_column", "target")] = y_test
                mlflow.evaluate(
                    model=f"runs:/{run_id_mlflow}/model",
                    data=eval_data,
                    targets=resultado_eda.get("target_column", "target"),
                    model_type="classifier" if tipo_problema == "classification" else "regressor",
                    evaluators=["default"],
                )
                log.info("[TrainingService] Evaluación MLflow completada (gráficos automáticos).")
            except Exception as eval_err:
                log.warning(f"[TrainingService] mlflow.evaluate falló: {eval_err}")

            # Genearación y subida de Gráficos complementarios 
            log.info("[TrainingService] [Fase 7/8] Generando gráficos complementarios")
            graficos = generar_graficos(
                modelo=modelo,
                X_test=X_test,
                y_test=y_test,
                tipo_problema=tipo_problema,
                dataset=dataset,
                directorio_salida=str(directorio_graficos),
            )
            for ruta_grafico in graficos:
                try:
                    mlflow.log_artifact(ruta_grafico, artifact_path="plots_custom")
                except Exception as plot_err:
                    log.warning(f"[TrainingService] No se pudo loguear gráfico {ruta_grafico}: {plot_err}")
            log.info(f"[TrainingService] Gráficos complementarios logueados: {len(graficos)}")

            # Subida del codigo de la pipeline a MLFlow
            log.info("[TrainingService] [Fase 8/8] Registrando código del pipeline")
            directorio_pipeline = os.path.join(os.path.dirname(__file__), "pipeline")
            if os.path.isdir(directorio_pipeline):
                for archivo in Path(directorio_pipeline).glob("*.py"):
                    try:
                        mlflow.log_artifact(str(archivo), artifact_path="code")
                    except Exception as code_err:
                        log.warning(f"[TrainingService] No se pudo loguear código {archivo}: {code_err}")
                log.info("[TrainingService] Código del pipeline registrado.")

            log.info(f"[TrainingService] MLflow run completado: {run_id_mlflow}")

        ########## Ultima fase: Actualizar estado del job en DynamoDB a COMPLETED ############
        log.info("[TrainingService] Pipeline completado exitosamente. Actualizando DynamoDB.")

        # Serializar métricas a string para DynamoDB
        metricas_str = json.dumps(metricas, ensure_ascii=False)

        actualizar_estado_job(
            config.dynamodb_jobs_table,
            job_id,
            "COMPLETED",
            algorithm=algoritmo,
            metrics=metricas_str,
            mlflow_run_id=run_id_mlflow or "",
            problem_type=tipo_problema,
        )

        log.info(f"[TrainingService] Job {job_id} completado con éxito.")
        return 0


    # Manejo Global de errores
    except Exception as error:
        log.error("[TrainingService] " + "=" * 60)
        log.error(f"[TrainingService] Error en el pipeline para job_id={job_id}")
        log.error(f"[TrainingService] Tipo: {type(error).__name__}")
        log.error(f"[TrainingService] Mensaje: {error}")
        log.error(f"[TrainingService] Traceback:\n{traceback.format_exc()}")
        log.error("[TrainingService] " + "=" * 60)

        # Si hay un run, reabrirlo para registrar el error
        if run_id_mlflow:
            try:
                with mlflow.start_run(run_id=run_id_mlflow):
                    mlflow.set_tag("status", "FAILED")
                    mlflow.log_param("error_message", str(error)[:500])
                    mlflow.log_dict({"traceback": traceback.format_exc()}, "errors/traceback.json")
                log.info(f"[TrainingService] Error registrado en MLflow run {run_id_mlflow}")
            except Exception as mlflow_err:
                log.warning(f"[TrainingService] No se pudo registrar error en MLflow: {mlflow_err}")

        # Intentar actualizar DynamoDB con FAILED
        try:
            error_msg = f"{type(error).__name__}: {str(error)}"
            if len(error_msg) > 1000:
                error_msg = error_msg[:997] + "..."

            actualizar_estado_job(
                config.dynamodb_jobs_table,
                job_id,
                "FAILED",
                error_message=error_msg,
                mlflow_run_id=run_id_mlflow or "",
            )
            log.info("[TrainingService] DynamoDB actualizado: status=FAILED")
        except Exception as dyn_error:
            log.error(f"[TrainingService] No se pudo actualizar DynamoDB con estado FAILED: {dyn_error}")

        return 1


###########################
#      Main Function      #
###########################
def main() -> int:
    """
    Función principal del TrainingService.
    Parse argumentos, carga configuración y ejecuta el pipeline.
    Returns:
        int: Código de salida (0=éxito, 1=fallo).
    """
    args = _parsear_argumentos()

    log = CloudWatchLogger.configure(
        log_group="Training-Server-PFG",
        log_stream=args.log_stream
    )
    log.info(f"[TrainingService] Inicio de ejecución. job_id={args.job_id}")

    try:
        config = cargar_configuracion()
    except EnvironmentError as error:
        log.critical(f"[TrainingService] Error de configuración: {error}")
        return 1

    resultado = _ejecutar_pipeline(args, config)

    # Forzar envío de todos los logs pendientes a CloudWatch antes de terminar
    import watchtower
    for handler in log.handlers:
        if isinstance(handler, watchtower.CloudWatchLogHandler):
            handler.flush()

    return resultado


if __name__ == "__main__":
    codigo_salida = main()
    sys.exit(codigo_salida)
