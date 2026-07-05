#!/bin/bash
set -e
set -o pipefail

###########################
#     Node Preparation    #
###########################
yum update -y
yum upgrade -y
yum install -y python3.12 python3.12-pip
mkdir /opt/mlflow


###########################
#   MlFlow Installation   #
###########################
cd /opt/mlflow
chown -R ec2-user:ec2-user /opt/mlflow
chmod -R 750 /opt/mlflow

# Crear y activar virtualenv para MLflow
python3.12 -m venv /opt/mlflow/venv
source /opt/mlflow/venv/bin/activate

# Instalar mlflow dentro del venv
python3.12 -m pip install mlflow
python3.12 -m pip install boto3


##################################
#  Configurar systemd mlflow     #
##################################
cat > /etc/systemd/system/mlflow.service << SYSTEMDEOF
[Unit]
Description=MLflow Tracking Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mlflow
Environment="PATH=/opt/mlflow/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/mlflow/venv/bin/mlflow server \
  --host 0.0.0.0 \
  --port ${LISTENER_PORT} \
  --default-artifact-root s3://${MLFLOW_ARTIFACT_BUCKET}/mlflow/artifacts \
  --backend-store-uri sqlite:///opt/mlflow/mlflow.db \
  --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMDEOF

systemctl daemon-reload
systemctl enable mlflow
systemctl start mlflow
