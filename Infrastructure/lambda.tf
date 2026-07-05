###########################
#     IAM Lambda Logic    #
###########################
data "aws_iam_policy_document" "lambda_assume_role_policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "iam_for_lambda" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.authorizer_lambda.name}"          = var.authorizer_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  name               = "${each.value.name}-Role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role_policy.json
}

resource "aws_iam_role_policy_attachment" "execution_policy" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.authorizer_lambda.name}"          = var.authorizer_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  role       = aws_iam_role.iam_for_lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaRole"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_policy" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.authorizer_lambda.name}"          = var.authorizer_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  role       = aws_iam_role.iam_for_lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  role       = aws_iam_role.iam_for_lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}


###################
# Networking Code #
###################
resource "aws_security_group" "lambda_sg" {
  for_each = {
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  name        = "${each.key}-SG"
  description = "Security Group that will be used in a lambda"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_egress_rule" "allow_egress_lambdas" {
  for_each = {
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  security_group_id = aws_security_group.lambda_sg[each.key].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1" # semantically equivalent to all ports
}


###########################
#  Lambda Creation Logic  #
###########################
resource "aws_lambda_function" "lambdas_creation" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.authorizer_lambda.name}"          = var.authorizer_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  function_name    = each.key
  runtime          = "python${each.value.python_version}"
  handler          = each.value.handler
  role             = aws_iam_role.iam_for_lambda[each.key].arn
  filename         = data.archive_file.zip_lambda_code[each.key].output_path # Archivo ZIP con tu código.
  source_code_hash = data.archive_file.zip_lambda_code[each.key].output_sha
  timeout          = 30

  environment {
    variables = local.environment_variables[each.key]
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda_logs[each.key].name
  }

  dynamic "vpc_config" {
    for_each = length(local.vpc_configurations[each.key]) > 0 ? [local.vpc_configurations[each.key]] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_groups
    }
  }
}


######################################
#   API Gateway Lambda Integration   #
######################################
resource "aws_lambda_permission" "lambda_permission" {
  for_each = {
    "${var.authentication_lambda.name}"      = var.authentication_lambda,
    "${var.get_training_status_lambda.name}" = var.get_training_status_lambda,
    "${var.delete_data_lambda.name}"         = var.delete_data_lambda
    "${var.training_request_lambda.name}"    = var.training_request_lambda
    "${var.get_prediction_lambda.name}"      = var.get_prediction_lambda
  }
  statement_id  = "AllowAPInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambdas_creation[each.key].arn
  principal     = "apigateway.amazonaws.com"

  # The /* part allows invocation from any stage, method and resource path
  # within API Gateway.
  source_arn = "${aws_api_gateway_rest_api.PFG_API.execution_arn}/*/*"
}

resource "aws_lambda_permission" "authorizer_permission" {
  statement_id  = "AllowAPIGatewayInvoke-Authorizer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambdas_creation[var.authorizer_lambda.name].arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.PFG_API.execution_arn}/*/*"
}


########################################
# Automaticlly Trigger Lambda Training #
########################################
resource "aws_cloudwatch_event_rule" "twice_a_month" {
  name                = "every-15days"
  schedule_expression = "rate(15 days)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.twice_a_month.name
  target_id = "${var.training_request_lambda.name}-Target"
  arn       = aws_lambda_function.lambdas_creation[var.training_request_lambda.name].arn
}

resource "aws_lambda_permission" "training_trigger_allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambdas_creation[var.training_request_lambda.name].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.twice_a_month.arn
}


##########################
#  DynamoDB IAM Policy   #
##########################
resource "aws_iam_policy" "lambda_dynamodb_policy" {
  name        = "lambda-dynamodb-users-access"
  description = "Allow Authentication Lambda to access the users table"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem"
        ]
        Effect   = "Allow"
        Resource = aws_dynamodb_table.users_table.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "auth_lambda_dynamodb" {
  role       = aws_iam_role.iam_for_lambda[var.authentication_lambda.name].name
  policy_arn = aws_iam_policy.lambda_dynamodb_policy.arn
}

resource "aws_iam_policy" "authorizer_dynamodb_policy" {
  name        = "authorizer-dynamodb-query-access"
  description = "Allow Authorizer Lambda to query users by api_key"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:Query"
        ]
        Effect = "Allow"
        Resource = [
          aws_dynamodb_table.users_table.arn,
          "${aws_dynamodb_table.users_table.arn}/index/api-key-index"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "authorizer_lambda_dynamodb" {
  role       = aws_iam_role.iam_for_lambda[var.authorizer_lambda.name].name
  policy_arn = aws_iam_policy.authorizer_dynamodb_policy.arn
}

resource "aws_iam_policy" "get_training_status_dynamodb_policy" {
  name        = "get-training-status-dynamodb-query-access"
  description = "Allow GetTrainingStatus Lambda to query training-jobs-table and its user-dataset-index GSI"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:Query"
        ]
        Effect = "Allow"
        Resource = [
          aws_dynamodb_table.training_jobs_table.arn,
          "${aws_dynamodb_table.training_jobs_table.arn}/index/user-dataset-index"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "get_training_status_dynamodb_attach" {
  role       = aws_iam_role.iam_for_lambda[var.get_training_status_lambda.name].name
  policy_arn = aws_iam_policy.get_training_status_dynamodb_policy.arn
}

# Política IAM para que DeleteData Lambda pueda eliminar objetos del bucket de datasets
resource "aws_iam_policy" "delete_data_s3_policy" {
  name        = "delete-data-s3-access"
  description = "Permite a la Lambda DeleteData eliminar objetos del bucket de datasets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Permiso para listar (aplica SOLO al bucket)
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.dataset_bucket.arn}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.dataset_bucket.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "delete_data_s3_attach" {
  role       = aws_iam_role.iam_for_lambda[var.delete_data_lambda.name].name
  policy_arn = aws_iam_policy.delete_data_s3_policy.arn
}

# Política IAM para que DeleteData Lambda pueda consultar y eliminar registros de training-jobs-table
resource "aws_iam_policy" "delete_data_dynamodb_policy" {
  name        = "delete-data-dynamodb-access"
  description = "Permite a la Lambda DeleteData consultar y eliminar registros de la tabla training-jobs-table y su GSI"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.training_jobs_table.arn,
          "${aws_dynamodb_table.training_jobs_table.arn}/index/user-dataset-index"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "delete_data_dynamodb_attach" {
  role       = aws_iam_role.iam_for_lambda[var.delete_data_lambda.name].name
  policy_arn = aws_iam_policy.delete_data_dynamodb_policy.arn
}

# Política IAM para que GetPrediction Lambda pueda consultar la tabla training-jobs-table y su GSI
resource "aws_iam_policy" "get_prediction_dynamodb_policy" {
  name        = "get-prediction-dynamodb-query-access"
  description = "Allow GetPrediction Lambda to query training-jobs-table and its user-dataset-index GSI"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = ["dynamodb:Query"]
        Effect = "Allow"
        Resource = [
          aws_dynamodb_table.training_jobs_table.arn,
          "${aws_dynamodb_table.training_jobs_table.arn}/index/user-dataset-index"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "get_prediction_dynamodb_attach" {
  role       = aws_iam_role.iam_for_lambda[var.get_prediction_lambda.name].name
  policy_arn = aws_iam_policy.get_prediction_dynamodb_policy.arn
}