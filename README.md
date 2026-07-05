# Diseño e Implementación de una Arquitectura en la Nube para la Gestión del Ciclo de Vida de Modelos Basados en Machine Learning

<p align="center">
  <img src=".images/etsist.png" alt="ETSISI UPM">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Go-1.25.3-00ADD8?logo=go" alt="Go">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Terraform-1.14.9-844FBA?logo=terraform" alt="Terraform">
  <img src="https://img.shields.io/badge/AWS-FF9900?logo=amazon-aws" alt="AWS">
  <img src="https://img.shields.io/badge/MLflow-0194E2?logo=mlflow" alt="MLflow">
  <img src="https://img.shields.io/badge/License-Open%20Source-green" alt="License">
</p>

## Descripción

Este proyecto propone el diseño y desarrollo de una arquitectura **MLOps nativa en la nube (AWS)** basada en un enfoque de **intervención humana nula** (*zero-touch pipeline*). El objetivo principal es automatizar integralmente los procesos de preparación de datos, entrenamiento, despliegue y mantenimiento predictivo de modelos de Machine Learning.

El flujo operativo se inicia automáticamente tras la ingesta de los datos finales, activando una fase de preprocesamiento inteligente donde agentes de Inteligencia Artificial y LLMs depuran y transforman la información para su optimización. A continuación, el sistema orquesta un proceso de **AutoML** que itera sobre múltiples algoritmos y ajusta dinámicamente los hiperparámetros para identificar el modelo con el mejor rendimiento. El modelo resultante es versionado y registrado de forma automática en **MLflow**, garantizando la trazabilidad completa de metadatos, parámetros y artefactos.

Para asegurar la fiabilidad a largo plazo, la plataforma integra un sistema de inferencia con monitorización continua de la degradación de los datos (*data drift*). Si las métricas de precisión caen por debajo de un umbral predefinido, la arquitectura dispara automáticamente un *pipeline* de reentrenamiento continuo (**Continuous Training**), fusionando los datos históricos con las nuevas observaciones.

## Arquitectura

<p align="center">
  <img src=".images/architecture.drawio.png" alt="Architecture">
</p>

### Componentes principales

- **API-CLI**: Cliente de línea de comandos desarrollado en Go (cobra) que interactúa con la API Gateway.
- **API Gateway**: Punto de entrada único a la plataforma. Expone 5 endpoints REST.
- **AWS Lambda**: 4 funciones Python 3.12 que orquestan autenticación, inicio de entrenamiento, consulta de estado y eliminación de datos.
- **Training EC2**: Instancia `t4g.small` que ejecuta la lógica de AutoML y un servicio FastAPI/uvicorn (puerto 8080) para recibir peticiones desde Lambda.
- **MLflow EC2**: Instancia `t4g.small` dedicada al tracking server de MLflow (puerto 8080), con artefactos almacenados en S3.
- **S3**: 3 buckets para datasets (`datasets-pfg-s3`), transferencia de código (`filestransfer-pfg-s3`) y artefactos de MLflow (`mlflowartifacts-pfg-s3`).
- **DynamoDB**: Tabla `users-auth-table` (modo `PAY_PER_REQUEST`) para autenticación y metadatos.
- **Terraform**: Infraestructura como código que despliega todos los recursos AWS.

## Stack tecnológico

| Capa | Tecnología | Versión | Propósito |
|------|-----------|---------|-----------|
| CLI | Go | 1.25.3 | Cliente de línea de comandos |
| API | AWS API Gateway | — | Punto de entrada REST |
| Serverless | AWS Lambda | Python 3.12 | Orquestación de operaciones |
| Compute | AWS EC2 (t4g.small) | Ubuntu 24.04 | Training Server + MLflow Server |
| Storage | AWS S3 | — | Datasets, artefactos, transferencia de código |
| Database | AWS DynamoDB | — | Metadatos de usuarios y estado |
| Training | Python 3.12 + scikit-learn | — | Motor de AutoML |
| Tracking | MLflow | 2.x | Versionado y registro de modelos |
| REST API | FastAPI + Uvicorn | — | Listener en Training Server (puerto 8080) |
| IaC | Terraform | 1.14.9 | Despliegue de infraestructura AWS |
| IA | OpenCode (API OpenAI) | — | Motor LLM para análisis de datasets y selección de algoritmos |

## Estructura del proyecto

```
ProyectoPFG/
├── API-CLI/              # CLI en Go (cobra)
│   └── go.mod            # Módulo Go 1.25.3 + cobra v1.10.1
├── LambdaCode/           # Funciones AWS Lambda (Python 3.12)
│   ├── Authentication/
│   ├── DeleteData/
│   ├── GetPrediction/
│   ├── GetTrainingStatus/
│   └── TrainingRequest/
├── TrainingServer/       # Servicios en EC2
│   ├── TrainingService/  # Lógica de AutoML + MLflow
│   └── ListenerREST/     # FastAPI/uvicorn (puerto 8080)
├── Infrastructure/       # Terraform (AWS)
│   ├── extrafiles/       # Scripts de bootstrap
│   │   ├── TrainingServer.sh
│   │   └── MLFlowServer.sh
│   └── *.tf              # Recursos AWS
├── TFG/                  # Memoria LaTeX
│   ├── capitulos/
│   ├── imagenes/
│   ├── main.tex
│   └── export.bib
└── Workflow/             # Documentación y notas de investigación
```

## Requisitos previos

- Cuenta de AWS con acceso programático configurado
- Terraform >= 1.14.9
- Go >= 1.25.3
- Python 3.12
- AWS CLI configurado (`aws configure`)

## Despliegue rápido

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd ProyectoPFG

# 2. Desplegar infraestructura AWS
cd Infrastructure
terraform init
terraform plan
terraform apply

# 3. Compilar CLI
cd ../API-CLI
go build -o api-cli .

# 4. Usar la plataforma
./api-cli --source <API_GATEWAY_URL> login
./api-cli --source <API_GATEWAY_URL> upload --dataset <path>
./api-cli --source <API_GATEWAY_URL> start-training --dataset-name <name>
./api-cli --source <API_GATEWAY_URL> delete --dataset-name <name>
```

> **Crítico**: Todos los comandos del CLI requieren la flag `--source` con la URL de la API Gateway.

## Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/auth?userName=<name>` | Autenticación de usuarios |
| PUT | `/upload?user=<name>&fileName=<name>` | Subida de datasets a S3 |
| POST | `/training-start` | Inicia entrenamiento AutoML |
| GET | `/get-status?datasetName=<name>&userName=<name>` | Estado del entrenamiento |
| DELETE | `/delete-data?datasetName=<name>&userName=<name>` | Elimina dataset y recursos asociados |

## Funcionamiento del pipeline

1. **Ingesta**: El usuario sube un dataset mediante el CLI → almacenamiento en S3 (`datasets-pfg-s3`).
2. **Trigger**: El usuario solicita inicio de entrenamiento mediante CLI → API Gateway → Lambda `TrainingRequest` → petición HTTP al Training EC2 (ListenerREST en puerto 8080).
3. **AutoML**: El Training Server ejecuta:
   - Preprocesamiento inteligente de datos.
   - Iteración sobre múltiples algoritmos de ML (scikit-learn).
   - Ajuste dinámico de hiperparámetros.
   - Selección del modelo con mejor rendimiento.
4. **Registro**: El mejor modelo se versiona automáticamente en MLflow, con metadatos, parámetros y artefactos almacenados en S3/DynamoDB.
5. **Monitorización**: El sistema de inferencia evalúa continuamente el rendimiento y detecta *data drift*.
6. **Reentrenamiento**: Si la precisión cae bajo el umbral configurado, se dispara automáticamente el *pipeline* de **Continuous Training**, fusionando datos históricos con nuevas observaciones.

## Características clave

- **Zero-touch pipeline**: Automatización completa desde la ingesta de datos hasta el despliegue y mantenimiento del modelo.
- **AutoML integrado**: Selección automática del mejor algoritmo y configuración de hiperparámetros sin intervención manual.
- **Trazabilidad total**: MLflow registra todos los experimentos, modelos, métricas y artefactos.
- **Serverless**: API Gateway + Lambda para escalabilidad elástica y bajo coste operativo.
- **Continuous Training**: Reentrenamiento automático ante degradación de datos (*data drift*).
- **Open Source**: Stack tecnológico 100% libre (Go BSD, Python PSF, Terraform MPL-2.0, MLflow Apache-2.0).

## Presupuesto y costes

| Concepto | Importe |
|----------|---------|
| Desarrollo (320h x 15 EUR/h) | 4.800,00 EUR |
| AWS mensual (2x t4g.small 24/7) | ~18,00 - 21,00 EUR/mes |
| Software y herramientas | 0,00 EUR (open source) |
| **Total proyecto (desarrollo + 1 año operación)** | **~5.016,00 - 5.052,00 EUR** |

> El coste puede reducirse drásticamente apagando instancias EC2 fuera de horas de uso o aprovechando la capa gratuita (Free Tier) de AWS durante el primer año.

## Problemas conocidos / TODO

- [ ] **Sesgo algorítmico**: El proceso AutoML no incluye actualmente métricas de *fairness*. Pendiente integrar librerías como `fairlearn` o `aif360`.
- [ ] **Privacidad**: No se ha implementado cifrado explícito con AWS KMS ni anonimización de datos sensibles.
- [ ] **Conectividad**: La plataforma requiere acceso a Internet, lo que limita su uso en zonas sin cobertura adecuada.
- [ ] **Balanceo de carga**: Actualmente una única instancia EC2 atiende las peticiones de entrenamiento. Pendiente evaluar auto-scaling o balanceo con ALB.
- [ ] **Memoria insuficiente (OOM)**: Debido a las limitaciones de la instancia `t4g.small` de la capa gratuita (1 GB RAM), el servidor MLflow puede ser terminado por el sistema (*OOM-killed*) al cargar modelos grandes o gestionar múltiples artefactos. Se recomienda utilizar una instancia con mayor capacidad de RAM (por ejemplo, `t4g.medium` o superior) para entornos de producción.

## Etapas de un modelo de Machine Learning (Contexto educativo)

A continuación se presentan las etapas genéricas del ciclo de vida de un modelo de ML, que sirven de marco teórico para el proyecto:

1. **Definición del Problema**: Identificación del problema que se va a abordar. Establecimiento de los objetivos comerciales y de rendimiento.

2. **Recopilación de Datos**: Recopilación de datos relevantes para el problema. Limpieza y preprocesamiento de datos.

3. **Exploración y Análisis de Datos**: Exploración y análisis estadístico de los datos. Identificación de patrones y relaciones.

4. **Ingeniería de Características**: Selección y transformación de variables relevantes. Creación de nuevas características que puedan mejorar el rendimiento.

5. **Selección del Modelo**: Elección del algoritmo o modelo de aprendizaje automático. Configuración de hiperparámetros iniciales.

6. **Entrenamiento del Modelo**: División del conjunto de datos en conjuntos de entrenamiento y prueba. Entrenamiento del modelo utilizando datos de entrenamiento.

7. **Validación y Ajuste de Hiperparámetros**: Evaluación del rendimiento del modelo en el conjunto de validación. Ajuste de hiperparámetros para mejorar el rendimiento.

8. **Evaluación del Modelo**: Evaluación final del modelo en el conjunto de prueba. Medición de métricas de rendimiento como precisión, recall, F1-score, etc.

9. **Despliegue del Modelo**: Integración del modelo en el entorno de producción. Monitoreo continuo del rendimiento del modelo.

10. **Mantenimiento y Actualización**: Actualización periódica del modelo para mantener su rendimiento. Manejo de cambios en los datos o en los requisitos comerciales.

## Licencia

Este proyecto utiliza un stack tecnológico 100% open source:

- **Go**: BSD-3-Clause
- **Python / scikit-learn / MLflow**: PSF / Apache-2.0
- **Terraform**: MPL-2.0
- **FastAPI / Uvicorn**: MIT

El código fuente del proyecto se distribuye bajo licencia abierta para fines académicos y de investigación.

---

<p align="center">
  <sub>Desarrollado como Trabajo Fin de Grado en la ETSISI - UPM</sub>
</p>
