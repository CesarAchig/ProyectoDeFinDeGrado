############################################
# Training Server Code Files Preparation   #
############################################
resource "null_resource" "trigger_zip_training_code" {
  triggers = {
    for i in fileset(var.training_service_code_path, "*") : i => sha1(file("${var.training_service_code_path}/${i}"))
  }
}

data "archive_file" "zip_code_training" {
  type        = "zip"
  output_path = "${var.temporal_folder}/${local.training_service_zip_name}"
  source_dir  = var.training_service_code_path
  depends_on  = [null_resource.trigger_zip_training_code]
}


#####################################
# API Server Code Files Preparation #
#####################################
resource "null_resource" "trigger_zip_api_code" {
  triggers = {
    for i in fileset(var.listener_rest_code_path, "*") : i => sha1(file("${var.listener_rest_code_path}/${i}"))
  }
}

data "archive_file" "zip_api_code" {
  type        = "zip"
  output_path = "${var.temporal_folder}/${local.listener_rest_zip_name}"
  source_dir  = var.listener_rest_code_path
  depends_on  = [null_resource.trigger_zip_api_code]
}


#####################################
#   Common Code Files Preparation   #
#####################################
resource "null_resource" "trigger_zip_common_code" {
  triggers = {
    for i in fileset(var.common_code_path, "*") : i => sha1(file("${var.common_code_path}/${i}"))
  }
}

data "archive_file" "zip_code_common" {
  type        = "zip"
  output_path = "${var.temporal_folder}/${local.common_code_zip_name}"
  source_dir  = var.common_code_path
  depends_on  = [null_resource.trigger_zip_common_code]
}


############################
# Lambdas Zips Preparation #
############################
resource "null_resource" "trigger_zip_lambdas_code" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.authorizer_lambda.name}"          = var.authorizer_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  triggers = {
    for i in fileset("${var.lambdas_folder_path}/${each.value.folder_name_code}", "*") : i => sha1(file("${var.lambdas_folder_path}/${each.value.folder_name_code}/${i}"))
  }
}

data "archive_file" "zip_lambda_code" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.authorizer_lambda.name}"          = var.authorizer_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  type        = "zip"
  output_path = "${var.temporal_folder}/${each.key}.zip"
  source_dir  = "${var.lambdas_folder_path}/${each.value.folder_name_code}"
  depends_on  = [null_resource.trigger_zip_lambdas_code]
}