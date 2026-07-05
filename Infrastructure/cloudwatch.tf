###########################
#     Local Variables     #
########################### 
locals {
  lambda_names = [
    var.authentication_lambda.name,
    var.authorizer_lambda.name,
    var.get_training_status_lambda.name,
    var.delete_data_lambda.name,
    var.training_request_lambda.name,
    var.get_prediction_lambda.name,
  ]
}


###########################
#   CloudWatch LogGroups  #
###########################
# LogGroups para las Lambdas (5 grupos)
resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = toset(local.lambda_names)

  name              = "${each.value}-PFG"
  retention_in_days = 7

  tags = {
    Name = "${each.value}-PFG"
  }
}

# LogGroup para el Training Server (EC2)
resource "aws_cloudwatch_log_group" "training_server_logs" {
  name              = "${var.training_server.name}-PFG"
  retention_in_days = 7

  tags = {
    Name = "${var.training_server.name}-PFG"
  }
}


##########################
#   Log Metric Filters   #
##########################
resource "aws_cloudwatch_log_metric_filter" "lambda_error_filters" {
  for_each = toset(local.lambda_names)

  name           = "${each.value}-ErrorFilter"
  pattern        = "\"[ERROR]\""
  log_group_name = aws_cloudwatch_log_group.lambda_logs[each.key].name

  metric_transformation {
    name      = "ErrorCount-${each.value}"
    namespace = "PFG/Errors"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "training_server_error_filter" {
  name           = "${var.training_server.name}-ErrorFilter"
  pattern        = "\"[ERROR]\""
  log_group_name = aws_cloudwatch_log_group.training_server_logs.name

  metric_transformation {
    name      = "ErrorCount-${var.training_server.name}"
    namespace = "PFG/Errors"
    value     = "1"
  }
}


###########################
#    SNS Notifications    #
###########################
resource "aws_sns_topic" "alarm_notifications" {
  name = "PFG-Alarm-Notifications"
}

resource "aws_sns_topic_subscription" "email_subscription" {
  topic_arn = aws_sns_topic.alarm_notifications.arn
  protocol  = "email"
  endpoint  = var.email_of_notification
}


###########################
#   CloudWatch Alarms     #
###########################
resource "aws_cloudwatch_metric_alarm" "lambda_error_alarms" {
  for_each = toset(local.lambda_names)

  alarm_name          = "${each.value}-ErrorAlarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ErrorCount-${each.value}"
  namespace           = "PFG/Errors"
  period              = 300
  statistic           = "Sum"
  threshold           = 2
  alarm_description   = "Alarm when [ERROR] pattern appears more than 2 times in 5 minutes in ${each.value}"
  alarm_actions       = [aws_sns_topic.alarm_notifications.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "training_server_error_alarm" {
  alarm_name          = "${var.training_server.name}-ErrorAlarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ErrorCount-${var.training_server.name}"
  namespace           = "PFG/Errors"
  period              = 300
  statistic           = "Sum"
  threshold           = 2
  alarm_description   = "Alarm when [ERROR] pattern appears more than 2 times in 5 minutes in ${var.training_server.name}"
  alarm_actions       = [aws_sns_topic.alarm_notifications.arn]
  treat_missing_data  = "notBreaching"
}
