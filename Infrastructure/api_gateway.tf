##########################
#   IAM Control APIGCW   #
##########################
data "aws_iam_policy_document" "apigw_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["apigateway.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_policy" "apigw_s3_policy" {
  name        = "apigw_s3_bucket_access"
  description = "This policy is created to enable the access to the s3 bucket where the datasets are keep it"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:PutObject"
        ]
        Effect = "Allow"
        Resource = [
          "${aws_s3_bucket.dataset_bucket.arn}/*"
        ]
      },
    ]
  })
}

resource "aws_iam_role" "apigw_s3_role" {
  name               = "${var.api_gateway_name}-role"
  assume_role_policy = data.aws_iam_policy_document.apigw_assume_role.json
}

resource "aws_iam_policy_attachment" "attach_apigw_bucket_policy" {
  name       = "Attach_apigw_bucket_policy_to_apigw_role"
  policy_arn = aws_iam_policy.apigw_s3_policy.arn
  roles      = [aws_iam_role.apigw_s3_role.name]
}


##########################
#  API GateWay Creation  #
##########################
resource "aws_api_gateway_rest_api" "PFG_API" {
  name               = var.api_gateway_name
  description        = "This is the API of the platform that controls the Lifecycle of machine learning models"
  binary_media_types = ["*/*"]
}


#########################
#   Lambda Authorizer   #
#########################
resource "aws_api_gateway_authorizer" "token_authorizer" {
  name                             = "TokenAuthorizer"
  rest_api_id                      = aws_api_gateway_rest_api.PFG_API.id
  authorizer_uri                   = aws_lambda_function.lambdas_creation[var.authorizer_lambda.name].invoke_arn
  authorizer_credentials           = aws_iam_role.apigw_authorizer_role.arn
  identity_source                  = "method.request.header.Authorization"
  type                             = "TOKEN"
  authorizer_result_ttl_in_seconds = 0
}

data "aws_iam_policy_document" "apigw_authorizer_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["apigateway.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "apigw_authorizer_role" {
  name               = "${var.api_gateway_name}-authorizer-role"
  assume_role_policy = data.aws_iam_policy_document.apigw_authorizer_assume_role.json
}

resource "aws_iam_role_policy" "apigw_authorizer_policy" {
  name = "${var.api_gateway_name}-authorizer-policy"
  role = aws_iam_role.apigw_authorizer_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.lambdas_creation[var.authorizer_lambda.name].arn
      }
    ]
  })
}


##########################
#  GateWay Push Changes  #
##########################
resource "aws_api_gateway_deployment" "getaway_deployment" {
  rest_api_id = aws_api_gateway_rest_api.PFG_API.id
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_integration.upload_integration_s3_resource,
      aws_api_gateway_method_response.api_method_s3_resource_response_200,
      aws_api_gateway_method_response.api_method_s3_resource_response_400,
      aws_api_gateway_method_response.api_method_s3_resource_response_500,
      aws_api_gateway_integration_response.upload_integration_s3_resource_response_200,
      aws_api_gateway_integration_response.upload_integration_s3_resource_response_400,
      aws_api_gateway_integration_response.upload_integration_s3_resource_response_500,
      aws_api_gateway_method.api_method_s3_resource,
      aws_api_gateway_resource.api_s3_resource,
      aws_api_gateway_integration.api_integration,
      aws_api_gateway_authorizer.token_authorizer
    ]))
  }


  depends_on = [
    aws_api_gateway_integration.upload_integration_s3_resource,
    aws_api_gateway_method_response.api_method_s3_resource_response_200,
    aws_api_gateway_method_response.api_method_s3_resource_response_400,
    aws_api_gateway_method_response.api_method_s3_resource_response_500,
    aws_api_gateway_integration_response.upload_integration_s3_resource_response_200,
    aws_api_gateway_integration_response.upload_integration_s3_resource_response_400,
    aws_api_gateway_integration_response.upload_integration_s3_resource_response_500,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "getaway_stage" {
  deployment_id = aws_api_gateway_deployment.getaway_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.PFG_API.id
  stage_name    = var.api_gateway_name
}

