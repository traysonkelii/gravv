variable "env" { type = string }
variable "alert_email" { type = string }
variable "api_service_name" { type = string }
variable "worker_service_name" { type = string }
variable "api_log_group" { type = string }
variable "worker_log_group" { type = string }

resource "aws_sns_topic" "alerts" { name = "gravv-${var.env}-alerts" }

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "gravv-${var.env}-api-5xx-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  threshold           = 2
  alarm_actions       = [aws_sns_topic.alerts.arn]
  metric_query {
    id          = "rate"
    expression  = "100 * errors / MAX([requests, 1])"
    label       = "5xx percent"
    return_data = true
  }
  metric_query {
    id = "errors"
    metric {
      metric_name = "5xxStatusResponses"
      namespace   = "AWS/AppRunner"
      period      = 60
      stat        = "Sum"
      dimensions  = { ServiceName = var.api_service_name }
    }
  }
  metric_query {
    id = "requests"
    metric {
      metric_name = "Requests"
      namespace   = "AWS/AppRunner"
      period      = 60
      stat        = "Sum"
      dimensions  = { ServiceName = var.api_service_name }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "gravv-${var.env}-api-p95-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 10
  threshold           = 1500
  metric_name         = "RequestLatency"
  namespace           = "AWS/AppRunner"
  period              = 60
  extended_statistic  = "p95"
  dimensions          = { ServiceName = var.api_service_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# Custom metrics from structured log lines (Section 13.7).
resource "aws_cloudwatch_log_metric_filter" "jobs_dead" {
  name           = "gravv-${var.env}-jobs-dead"
  log_group_name = var.worker_log_group
  pattern        = "{ $.event = \"job_dead\" }"
  metric_transformation {
    name      = "jobs_dead_total"
    namespace = "Gravv/${var.env}"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "queue_depth" {
  name           = "gravv-${var.env}-queue-depth"
  log_group_name = var.worker_log_group
  pattern        = "{ $.event = \"jobs_queue_depth\" }"
  metric_transformation {
    name      = "jobs_queue_depth"
    namespace = "Gravv/${var.env}"
    value     = "$.jobs_queue_depth"
  }
}

resource "aws_cloudwatch_metric_alarm" "dead_job" {
  alarm_name          = "gravv-${var.env}-dead-job"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "jobs_dead_total"
  namespace           = "Gravv/${var.env}"
  period              = 300
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "queue_depth" {
  alarm_name          = "gravv-${var.env}-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 15
  threshold           = 200
  metric_name         = "jobs_queue_depth"
  namespace           = "Gravv/${var.env}"
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "worker_unhealthy" {
  alarm_name          = "gravv-${var.env}-worker-unhealthy"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  threshold           = 1
  metric_name         = "ActiveInstances"
  namespace           = "AWS/AppRunner"
  period              = 60
  statistic           = "Minimum"
  dimensions          = { ServiceName = var.worker_service_name }
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

output "topic_arn" { value = aws_sns_topic.alerts.arn }
