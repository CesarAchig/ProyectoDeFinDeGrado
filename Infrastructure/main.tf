###########################
#   Terraform Providers   #
###########################
terraform {
  backend "local" {
    path = "/tmp/localstate.tfstate"
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}


##########################
#   Global Data Blocks   #
##########################
data "aws_region" "current" {}

data "aws_subnet" "my_subnet" {
  id = var.subnet_id
}

data "aws_route_tables" "vpc_rts" {
  vpc_id = var.vpc_id
}


###########################
#     Local Variables     #
###########################
locals {
  training_service_zip_name = "training_code.zip"

  listener_rest_zip_name = "listener_code.zip"

  common_code_zip_name = "common_code.zip"

  dynamodb_jobs_table_name = "training-jobs-table"

  environment_variables = {
    (var.authentication_lambda.name) = {
      "USERS_TABLE_NAME" = aws_dynamodb_table.users_table.name
    }
    (var.authorizer_lambda.name) = {
      "USERS_TABLE_NAME" = aws_dynamodb_table.users_table.name
    }
    (var.get_training_status_lambda.name) = {
      "MLFLOW_SERVER_IP"         = aws_instance.mlflow_server.private_ip
      "TRAINING_JOBS_TABLE_NAME" = local.dynamodb_jobs_table_name
    }
    (var.delete_data_lambda.name) = {
      "DATASET_BUCKET_NAME"      = "${aws_s3_bucket.dataset_bucket.bucket}"
      "MLFLOW_SERVER_IP"         = aws_instance.mlflow_server.private_ip
      "TRAINING_JOBS_TABLE_NAME" = local.dynamodb_jobs_table_name
    }
    (var.training_request_lambda.name) = {
      "TRAINING_SERVER_IP"            = aws_instance.training_server.private_ip
      "TRAINING_SERVER_LISTENER_PORT" = var.training_server.ingress_ports
    }
    (var.get_prediction_lambda.name) = {
      "TRAINING_SERVER_IP"            = aws_instance.training_server.private_ip
      "TRAINING_SERVER_LISTENER_PORT" = var.training_server.ingress_ports
      "TRAINING_JOBS_TABLE_NAME"      = local.dynamodb_jobs_table_name
    }
  }

  vpc_configurations = {
    (var.authentication_lambda.name) = {}
    (var.authorizer_lambda.name)     = {}
    (var.get_training_status_lambda.name) = {
      "subnet_ids"      = [var.subnet_id]
      "security_groups" = [aws_security_group.lambda_sg[var.get_training_status_lambda.name].id]
    }
    (var.delete_data_lambda.name) = {
      "subnet_ids"      = [var.subnet_id]
      "security_groups" = [aws_security_group.lambda_sg[var.delete_data_lambda.name].id]
    }
    (var.training_request_lambda.name) = {
      "subnet_ids"      = [var.subnet_id]
      "security_groups" = [aws_security_group.lambda_sg[var.training_request_lambda.name].id]
    }
    (var.get_prediction_lambda.name) = {
      "subnet_ids"      = [var.subnet_id]
      "security_groups" = [aws_security_group.lambda_sg[var.get_prediction_lambda.name].id]
    }
  }

  method_request_parameters = {
    (var.authentication_lambda.name) = var.authentication_lambda.require_parameters == "" ? {} : {
      for i in split(",", var.authentication_lambda.require_parameters) : "method.request.querystring.${i}" => true
    }
    (var.authorizer_lambda.name) = {}
    (var.get_training_status_lambda.name) = var.get_training_status_lambda.require_parameters == "" ? {} : {
      for i in split(",", var.get_training_status_lambda.require_parameters) : "method.request.querystring.${i}" => true
    }
    (var.delete_data_lambda.name) = var.delete_data_lambda.require_parameters == "" ? {} : {
      for i in split(",", var.delete_data_lambda.require_parameters) : "method.request.querystring.${i}" => true
    }
    (var.training_request_lambda.name) = var.training_request_lambda.require_parameters == "" ? {} : {
      for i in split(",", var.training_request_lambda.require_parameters) : "method.request.querystring.${i}" => true
    }
    (var.get_prediction_lambda.name) = {}
  }
}
