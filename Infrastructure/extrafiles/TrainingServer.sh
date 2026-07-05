#!/bin/bash
set -e
set -o pipefail

###########################
#    Update the system    #
###########################
yum update -y
yum upgrade -y
yum install -y python3.12 python3.12-pip


####################################
# Prepare the Common Shared Code   #
####################################
mkdir -p /opt/training-server/common
cd /opt/training-server/common
aws s3 cp s3://${BUCKET_FILESTRANSFER_NAME}/${COMMON_CODE_ZIP_NAME} .
unzip ${COMMON_CODE_ZIP_NAME}


################################
# Prepare the Training Service #
################################
mkdir -p /opt/training-server/training-service
cd /opt/training-server/training-service
aws s3 cp s3://${BUCKET_FILESTRANSFER_NAME}/${TRAINING_CODE_ZIP_NAME} .
unzip ${TRAINING_CODE_ZIP_NAME}

# Crear y activar virtualenv para el training-service
python3.12 -m venv /opt/training-server/training-service/venv
source /opt/training-server/training-service/venv/bin/activate

# Instalar dependencias del training-service dentro del venv
python3.12 -m pip install -r requirements.txt


#############################
# Prepare the Listener REST #
#############################
mkdir -p /opt/training-server/listener-rest
cd /opt/training-server/listener-rest
aws s3 cp s3://${BUCKET_FILESTRANSFER_NAME}/${LISTENER_CODE_ZIP_NAME} .
unzip ${LISTENER_CODE_ZIP_NAME}

# Instalar dependencias del listener-rest en el mismo venv compartido
source /opt/training-server/training-service/venv/bin/activate
python3.12 -m pip install -r requirements.txt


###########################
#  Crear directorio jobs  #
###########################
mkdir -p /opt/jobs


##################################
#  Configurar systemd listener   #
##################################
cat > /etc/systemd/system/listener-rest.service << SYSTEMDEOF
[Unit]
Description=Listener REST Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/training-server/listener-rest
Environment="PATH=/opt/training-server/training-service/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/training-server/training-service:/opt/training-server"
Environment="MLFLOW_SERVER_IP=${MLFLOW_SERVER_IP}"
Environment="DATASET_BUCKET_NAME=${DATASET_BUCKET_NAME}"
Environment="DYNAMODB_JOBS_TABLE=${DYNAMODB_JOBS_TABLE}"
Environment="OPENCODE_API_KEY=${OPENCODE_API_KEY}"
ExecStart=/opt/training-server/training-service/venv/bin/uvicorn main:app --host 0.0.0.0 --port ${LISTENER_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMDEOF

systemctl daemon-reload
systemctl enable listener-rest
systemctl start listener-rest

