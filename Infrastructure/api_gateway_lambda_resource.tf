################################
# Creation of the API Resouces #
################################
resource "aws_api_gateway_resource" "api_lambda_resource" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  parent_id   = aws_api_gateway_rest_api.PFG_API.root_resource_id
  path_part   = each.value.endpoint_name
}


###############################
# Creation of the API Methods #
###############################
resource "aws_api_gateway_method" "api_method_lambda_resource" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  rest_api_id        = aws_api_gateway_rest_api.PFG_API.id
  resource_id        = aws_api_gateway_resource.api_lambda_resource[each.key].id
  http_method        = each.value.http_mehtod
  authorization      = each.key == var.authentication_lambda.name ? "NONE" : "CUSTOM"
  authorizer_id      = each.key == var.authentication_lambda.name ? null : aws_api_gateway_authorizer.token_authorizer.id
  request_parameters = local.method_request_parameters[each.key]
}


###################################
#   Creation of Method Responses  #
###################################
resource "aws_api_gateway_method_response" "api_method_lambda_resource_response_200" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  resource_id = aws_api_gateway_resource.api_lambda_resource[each.key].id
  http_method = each.value.http_mehtod
  status_code = "200"
  depends_on  = [aws_api_gateway_method.api_method_lambda_resource]
}

resource "aws_api_gateway_method_response" "api_method_lambda_resource_response_400" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  resource_id = aws_api_gateway_resource.api_lambda_resource[each.key].id
  http_method = each.value.http_mehtod
  status_code = "400"
  depends_on  = [aws_api_gateway_method.api_method_lambda_resource]
}


###################################
# Creation of the API Integration #
###################################
resource "aws_api_gateway_integration" "api_integration" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  rest_api_id             = aws_api_gateway_rest_api.PFG_API.id
  resource_id             = aws_api_gateway_resource.api_lambda_resource[each.key].id
  http_method             = each.value.http_mehtod
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.lambdas_creation[each.key].invoke_arn

  depends_on = [aws_api_gateway_method.api_method_lambda_resource]
}
