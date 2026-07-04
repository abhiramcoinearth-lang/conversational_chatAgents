resource "aws_cloudwatch_log_group" "app" {
  name              = "/chatagent/app"
  retention_in_days = 14
}

# Alarm: instance status check failed (hardware/reachability)
resource "aws_cloudwatch_metric_alarm" "status_check" {
  alarm_name          = "chatagent-status-check-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "EC2 status check failed for the chat agent instance"
  dimensions          = { InstanceId = aws_instance.this.id }
}

# Alarm: sustained high CPU
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "chatagent-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 90
  alarm_description   = "CPU > 90% for 15 minutes on the chat agent instance"
  dimensions          = { InstanceId = aws_instance.this.id }
}
