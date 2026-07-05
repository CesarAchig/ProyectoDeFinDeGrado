################################
# Creation of the API Resouces #
################################
resource "aws_api_gateway_resource" "api_s3_resource" {
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  parent_id   = aws_api_gateway_rest_api.PFG_API.root_resource_id
  path_part   = var.api_gateaway_s3_resource.endpoint_name
}

###############################
# Creation of the API Methods #
###############################
resource "aws_api_gateway_method" "api_method_s3_resource" {
  rest_api_id   = aws_api_gateway_rest_api.PFG_API.id
  resource_id   = aws_api_gateway_resource.api_s3_resource.id
  http_method   = var.api_gateaway_s3_resource.http_mehtod
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.token_authorizer.id
  request_parameters = {
    "method.request.querystring.${var.api_gateaway_s3_resource.param_query_name_filename}" = true,
    "method.request.querystring.${var.api_gateaway_s3_resource.param_query_name_username}" = true,
    "method.request.header.Content-Type"                                                   = false
  }
}

resource "aws_api_gateway_method_response" "api_method_s3_resource_response_200" {
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  resource_id = aws_api_gateway_resource.api_s3_resource.id
  http_method = var.api_gateaway_s3_resource.http_mehtod
  status_code = "200"
  depends_on  = [aws_api_gateway_method.api_method_s3_resource]
}

resource "aws_api_gateway_method_response" "api_method_s3_resource_response_400" {
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  resource_id = aws_api_gateway_resource.api_s3_resource.id
  http_method = var.api_gateaway_s3_resource.http_mehtod
  status_code = "400"
  depends_on  = [aws_api_gateway_method.api_method_s3_resource]
}

resource "aws_api_gateway_method_response" "api_method_s3_resource_response_500" {
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  resource_id = aws_api_gateway_resource.api_s3_resource.id
  http_method = var.api_gateaway_s3_resource.http_mehtod
  status_code = "500"
  depends_on  = [aws_api_gateway_method.api_method_s3_resource]
}


###################################
# Creation of the API Integration #
###################################
resource "aws_api_gateway_integration" "upload_integration_s3_resource" {
  rest_api_id             = aws_api_gateway_rest_api.PFG_API.id
  resource_id             = aws_api_gateway_resource.api_s3_resource.id
  http_method             = var.api_gateaway_s3_resource.http_mehtod
  type                    = "AWS"
  integration_http_method = "PUT"

  uri         = "arn:aws:apigateway:eu-west-1:s3:path/${aws_s3_bucket.dataset_bucket.bucket}/{${var.api_gateaway_s3_resource.param_query_name_username}}/{${var.api_gateaway_s3_resource.param_query_name_filename}}"
  credentials = aws_iam_role.apigw_s3_role.arn

  passthrough_behavior = "WHEN_NO_TEMPLATES"
  content_handling     = "CONVERT_TO_BINARY"

  request_parameters = {
    "integration.request.path.${var.api_gateaway_s3_resource.param_query_name_filename}" = "method.request.querystring.${var.api_gateaway_s3_resource.param_query_name_filename}"
    "integration.request.path.${var.api_gateaway_s3_resource.param_query_name_username}" = "context.authorizer.username"
    "integration.request.header.Content-Type"                                            = "method.request.header.Content-Type"
  }

  depends_on = [aws_api_gateway_method.api_method_s3_resource]
}

resource "aws_api_gateway_integration_response" "upload_integration_s3_resource_response_200" {
  rest_api_id       = aws_api_gateway_rest_api.PFG_API.id
  resource_id       = aws_api_gateway_resource.api_s3_resource.id
  http_method       = var.api_gateaway_s3_resource.http_mehtod
  status_code       = aws_api_gateway_method_response.api_method_s3_resource_response_200.status_code
  selection_pattern = "2\\d{2}"
  depends_on        = [aws_api_gateway_integration.upload_integration_s3_resource]
}
resource "aws_api_gateway_integration_response" "upload_integration_s3_resource_response_400" {
  rest_api_id       = aws_api_gateway_rest_api.PFG_API.id
  resource_id       = aws_api_gateway_resource.api_s3_resource.id
  http_method       = var.api_gateaway_s3_resource.http_mehtod
  status_code       = aws_api_gateway_method_response.api_method_s3_resource_response_400.status_code
  selection_pattern = "4\\d{2}"
  depends_on        = [aws_api_gateway_integration.upload_integration_s3_resource]
}

resource "aws_api_gateway_integration_response" "upload_integration_s3_resource_response_500" {
  rest_api_id       = aws_api_gateway_rest_api.PFG_API.id
  resource_id       = aws_api_gateway_resource.api_s3_resource.id
  http_method       = var.api_gateaway_s3_resource.http_mehtod
  status_code       = aws_api_gateway_method_response.api_method_s3_resource_response_500.status_code
  selection_pattern = "5\\d{2}"
  depends_on        = [aws_api_gateway_integration.upload_integration_s3_resource]
}
