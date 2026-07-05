###########################
#    General Variables    #
###########################
aws_region                 = "eu-west-1"
temporal_folder            = "./tmp"
lambdas_folder_path        = "../LambdaCode"
training_service_code_path = "../TrainingServer/TrainingService"
listener_rest_code_path    = "../TrainingServer/ListenerREST"
common_code_path           = "../TrainingServer/common"
vpc_id                     = "mock-vpc-id"
subnet_id                  = "mock-subnet-id"


###########################
#       S3 Variables      #
###########################
datasets_s3 = {
  name = "mock-datasets-pfg-s3"
}

filestransfer_s3 = {
  name = "mock-filestransfer-pfg-s3"
}

mlflow_artifacts_s3 = {
  name = "mock-mlflowartifacts-pfg-s3"
}


##########################
#  ApiGateway Variables  #
##########################
api_gateway_name = "PFG-API"
api_gateaway_s3_resource = {
  "endpoint_name"             = "upload"
  "http_mehtod"               = "PUT"
  "param_query_name_username" = "userName"
  "param_query_name_filename" = "fileName"
}
api_gateaway_ec2_resource = {
  "endpoint_name" = "traingstart"
  "http_mehtod"   = "POST"
}


###########################
#       EC2 Variables     # 
###########################
training_server = {
  name           = "Training-Server"
  ami            = "mock-ami-id"
  instance_type  = "t4g.small"
  user_data_path = "./extrafiles/TrainingServer.sh"
  ingress_ports  = "8080"
}

mlflow_server = {
  name           = "MLFlow-Server"
  ami            = "mock-ami-id"
  instance_type  = "t4g.small"
  user_data_path = "./extrafiles/MLFlowServer.sh"
  ingress_ports  = "8080"
}


###########################
#     Lamba Variables     #
###########################
authentication_lambda = {
  name               = "Authentication-Lambda"
  python_version     = "3.12"
  handler            = "main.lambda_handler"
  folder_name_code   = "Authentication"
  endpoint_name      = "auth"
  http_mehtod        = "GET"
  require_parameters = "userName"
}

get_training_status_lambda = {
  name               = "StatusTraining-Lambda"
  python_version     = "3.12"
  handler            = "main.lambda_handler"
  folder_name_code   = "GetTrainingStatus"
  endpoint_name      = "get-status"
  http_mehtod        = "GET"
  require_parameters = "datasetName,userName"
}

delete_data_lambda = {
  name               = "DeleteData-Lambda"
  python_version     = "3.12"
  handler            = "main.lambda_handler"
  folder_name_code   = "DeleteData"
  endpoint_name      = "delete-data"
  http_mehtod        = "DELETE"
  require_parameters = "datasetName,userName"
}

training_request_lambda = {
  name               = "TrainingRequest-Lambda"
  python_version     = "3.12"
  handler            = "main.lambda_handler"
  folder_name_code   = "TrainingRequest"
  endpoint_name      = "training-start"
  http_mehtod        = "POST"
  require_parameters = ""
}

authorizer_lambda = {
  name               = "Authorizer-Lambda"
  python_version     = "3.12"
  handler            = "main.lambda_handler"
  folder_name_code   = "Authorizer"
  endpoint_name      = ""
  http_mehtod        = ""
  require_parameters = ""
}

get_prediction_lambda = {
  name               = "GetPrediction-Lambda"
  python_version     = "3.12"
  handler            = "main.lambda_handler"
  folder_name_code   = "GetPrediction"
  endpoint_name      = "get-prediction"
  http_mehtod        = "POST"
  require_parameters = ""
}


###########################
#    OpenCode Variables   #
###########################
opencode_api_key = "mock-opencode-api-key"


###########################
#           SNS           #
###########################
email_of_notification = "mock-email@example.com"