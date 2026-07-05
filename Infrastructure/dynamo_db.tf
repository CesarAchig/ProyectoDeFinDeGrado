##########################
#   DynamoDB Users Table #
##########################
resource "aws_dynamodb_table" "users_table" {
  name         = "users-auth-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "username"

  attribute {
    name = "username"
    type = "S"
  }

  attribute {
    name = "api_key"
    type = "S"
  }

  global_secondary_index {
    name            = "api-key-index"
    hash_key        = "api_key"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false
  }

  tags = {
    Name = "users-auth-table"
  }
}


##########################
# DynamoDB Training Jobs #
##########################
resource "aws_dynamodb_table" "training_jobs_table" {
  name         = local.dynamodb_jobs_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  attribute {
    name = "user_name"
    type = "S"
  }

  attribute {
    name = "dataset_name"
    type = "S"
  }

  global_secondary_index {
    name            = "user-dataset-index"
    hash_key        = "user_name"
    range_key       = "dataset_name"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false
  }

  tags = {
    Name = local.dynamodb_jobs_table_name
  }
}
