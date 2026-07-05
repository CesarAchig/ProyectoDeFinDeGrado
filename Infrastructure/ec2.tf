#########################
#        IAM EC2        #
#########################
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy" "ssm_policy" {
  arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_policy" "filestransfer_bucket_access" {
  name        = "filestransfer_bucket_access"
  description = "This policy is created to enable the access to download and upload files to the bucket of filestransfer"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.filestransfer_bucket.arn}/*"]
      },
    ]
  })
}

resource "aws_iam_policy" "mlflow_artifact_bucket_access" {
  name        = "mlflow_artifact_bucket_access"
  description = "This policy is created to enable the access to download and upload files to the bucket of mlflow artifacts"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.mlflow_artifacts_bucket.arn}/*"]
      },
      {
        Action = [
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [aws_s3_bucket.mlflow_artifacts_bucket.arn]
      },
    ]
  })
}

# Política para que el Training Server acceda a DynamoDB (tabla de trabajos)
resource "aws_iam_policy" "training_server_dynamodb_policy" {
  name        = "training_server_dynamodb_policy"
  description = "Permite al Training Server leer y escribir en la tabla de trabajos de entrenamiento"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Effect = "Allow"
        Resource = [
          aws_dynamodb_table.training_jobs_table.arn,
          "${aws_dynamodb_table.training_jobs_table.arn}/index/*"
        ]
      },
    ]
  })
}

# Política para que el Training Server lea datasets del bucket S3
resource "aws_iam_policy" "datasets_bucket_access" {
  name        = "datasets_bucket_access"
  description = "Permite al Training Server descargar datasets desde el bucket de datasets"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.dataset_bucket.arn}/*"]
      },
    ]
  })
}

resource "aws_iam_policy" "ec2_cloudwatch_logs" {
  name        = "training-server-cloudwatch-logs"
  description = "Permite al Training Server escribir logs en CloudWatch Logs"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:*:*:log-group:${var.training_server.name}-PFG",
          "arn:aws:logs:*:*:log-group:${var.training_server.name}-PFG:log-stream:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role" "ec2_role" {
  for_each = {
    "${var.training_server.name}" = var.training_server,
    "${var.mlflow_server.name}"   = var.mlflow_server
  }
  name               = "EC2-${each.value.name}-Role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_instance_profile" "ec2_instance_profile" {
  for_each = {
    "${var.training_server.name}" = var.training_server,
    "${var.mlflow_server.name}"   = var.mlflow_server
  }
  name = "${each.value.name}-instanceprofile"
  role = aws_iam_role.ec2_role[each.key].name
}

resource "aws_iam_policy_attachment" "attach_ssm_policy" {
  name       = "Attach_ssm_policy_to_ec2_role"
  policy_arn = data.aws_iam_policy.ssm_policy.arn
  roles      = [aws_iam_role.ec2_role[var.training_server.name].name, aws_iam_role.ec2_role[var.mlflow_server.name].name]
}

resource "aws_iam_policy_attachment" "attach_filestransfer_policy" {
  name       = "Attach_filestransfer_policy_to_ec2_role"
  policy_arn = aws_iam_policy.filestransfer_bucket_access.arn
  roles      = [aws_iam_role.ec2_role[var.training_server.name].name, aws_iam_role.ec2_role[var.mlflow_server.name].name]
}

resource "aws_iam_policy_attachment" "attach_mlflowartifacts_policy" {
  name       = "Attach_mlflowartifacts__policy_to_ec2_role"
  policy_arn = aws_iam_policy.mlflow_artifact_bucket_access.arn
  roles      = [aws_iam_role.ec2_role[var.mlflow_server.name].name, aws_iam_role.ec2_role[var.training_server.name].name]
}

resource "aws_iam_policy_attachment" "attach_dynamodb_policy" {
  name       = "Attach_dynamodb_policy_to_training_server"
  policy_arn = aws_iam_policy.training_server_dynamodb_policy.arn
  roles      = [aws_iam_role.ec2_role[var.training_server.name].name]
}

resource "aws_iam_policy_attachment" "attach_datasets_bucket_policy" {
  name       = "Attach_datasets_bucket_policy_to_training_server"
  policy_arn = aws_iam_policy.datasets_bucket_access.arn
  roles      = [aws_iam_role.ec2_role[var.training_server.name].name]
}

resource "aws_iam_policy_attachment" "attach_ec2_cloudwatch_logs" {
  name       = "Attach_cloudwatch_logs_to_training_server"
  policy_arn = aws_iam_policy.ec2_cloudwatch_logs.arn
  roles      = [aws_iam_role.ec2_role[var.training_server.name].name]
}


###################
# Networking Code #
###################
resource "aws_security_group" "security_group" {
  for_each = {
    "${var.training_server.name}" = var.training_server,
    "${var.mlflow_server.name}"   = var.mlflow_server
  }
  name        = "${each.value.name}-SG"
  description = "This SG will be to control the inputs and ouput of the instance ${each.value.name}"
  vpc_id      = var.vpc_id
  tags = {
    Name = "${each.value.name}-SG"
  }
}

resource "aws_vpc_security_group_ingress_rule" "ingress_rules_training_server" {
  for_each          = toset([for etiqueta in split(",", var.training_server.ingress_ports) : trimspace(etiqueta)])
  security_group_id = aws_security_group.security_group[var.training_server.name].id
  cidr_ipv4         = data.aws_subnet.my_subnet.cidr_block
  from_port         = each.value
  ip_protocol       = "tcp"
  to_port           = each.value
}

resource "aws_vpc_security_group_ingress_rule" "ingress_rules_mlflow_server" {
  for_each          = toset([for etiqueta in split(",", var.mlflow_server.ingress_ports) : trimspace(etiqueta)])
  security_group_id = aws_security_group.security_group[var.mlflow_server.name].id
  cidr_ipv4         = data.aws_subnet.my_subnet.cidr_block
  from_port         = each.value
  ip_protocol       = "tcp"
  to_port           = each.value
}

resource "aws_vpc_security_group_egress_rule" "allow_all" {
  for_each = {
    "${var.training_server.name}" = var.training_server,
    "${var.mlflow_server.name}"   = var.mlflow_server
  }
  security_group_id = aws_security_group.security_group[each.key].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1" # semantically equivalent to all ports
}


##########################
# MLFlow Server Instance #
##########################
resource "aws_instance" "mlflow_server" {
  ami                         = var.mlflow_server.ami
  instance_type               = var.mlflow_server.instance_type
  iam_instance_profile        = aws_iam_instance_profile.ec2_instance_profile[var.mlflow_server.name].name
  vpc_security_group_ids      = [aws_security_group.security_group[var.mlflow_server.name].id]
  associate_public_ip_address = "true"
  subnet_id                   = var.subnet_id
  user_data = templatefile("${var.mlflow_server.user_data_path}", {
    BUCKET_FILESTRANSFER_NAME = aws_s3_bucket.filestransfer_bucket.bucket
    LISTENER_PORT             = var.mlflow_server.ingress_ports
    MLFLOW_ARTIFACT_BUCKET    = aws_s3_bucket.mlflow_artifacts_bucket.bucket
  })
  tags = {
    "Name" = var.mlflow_server.name
  }
  depends_on = [aws_s3_object.training_service_code_upload, aws_s3_object.api_listener_code_upload, aws_dynamodb_table.training_jobs_table]
}


############################
# Training Server Instance #
############################
resource "aws_instance" "training_server" {
  ami                         = var.training_server.ami
  instance_type               = var.training_server.instance_type
  iam_instance_profile        = aws_iam_instance_profile.ec2_instance_profile[var.training_server.name].name
  vpc_security_group_ids      = [aws_security_group.security_group[var.training_server.name].id]
  associate_public_ip_address = "true"
  subnet_id                   = var.subnet_id
  user_data = templatefile("${var.training_server.user_data_path}", {
    BUCKET_FILESTRANSFER_NAME = aws_s3_bucket.filestransfer_bucket.bucket
    TRAINING_CODE_ZIP_NAME    = local.training_service_zip_name
    LISTENER_CODE_ZIP_NAME    = local.listener_rest_zip_name
    COMMON_CODE_ZIP_NAME      = local.common_code_zip_name
    LISTENER_PORT             = var.training_server.ingress_ports
    MLFLOW_ARTIFACT_BUCKET    = aws_s3_bucket.mlflow_artifacts_bucket.bucket
    OPENCODE_API_KEY          = var.opencode_api_key
    DATASET_BUCKET_NAME       = aws_s3_bucket.dataset_bucket.bucket
    MLFLOW_SERVER_IP          = aws_instance.mlflow_server.private_ip
    DYNAMODB_JOBS_TABLE       = local.dynamodb_jobs_table_name
  })
  tags = {
    "Name" = var.training_server.name
  }
  depends_on = [aws_s3_object.training_service_code_upload, aws_s3_object.api_listener_code_upload, aws_s3_object.common_code_upload, aws_dynamodb_table.training_jobs_table, aws_instance.mlflow_server]
}
