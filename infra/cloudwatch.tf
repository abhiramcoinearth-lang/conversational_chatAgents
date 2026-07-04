resource "aws_cloudwatch_log_group" "app" {
  name              = "/chatagent/app"
  retention_in_days = 14
}

# ------------------------------------------------------------------------------
# Operational dashboard: EC2 host metrics, alarm status, and app/LLM logs.
# ------------------------------------------------------------------------------
resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = "chatagent"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "text", x = 0, y = 0, width = 24, height = 1,
        properties = { markdown = "# Chat Agent Platform — ${var.domain}  ·  ${var.instance_type} (T4)  ·  ${var.region}" }
      },
      {
        type = "metric", x = 0, y = 1, width = 8, height = 6,
        properties = {
          title   = "CPU Utilization (%)",
          view    = "timeSeries", region = var.region, period = 60,
          metrics = [["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.this.id, { stat = "Average" }]]
        }
      },
      {
        type = "metric", x = 8, y = 1, width = 8, height = 6,
        properties = {
          title  = "Network (bytes)",
          view   = "timeSeries", region = var.region, period = 60,
          metrics = [
            ["AWS/EC2", "NetworkIn", "InstanceId", aws_instance.this.id, { stat = "Average", label = "In" }],
            ["AWS/EC2", "NetworkOut", "InstanceId", aws_instance.this.id, { stat = "Average", label = "Out" }]
          ]
        }
      },
      {
        type = "metric", x = 16, y = 1, width = 8, height = 6,
        properties = {
          title  = "EBS throughput (bytes)",
          view   = "timeSeries", region = var.region, period = 300,
          metrics = [
            ["AWS/EC2", "EBSReadBytes", "InstanceId", aws_instance.this.id, { stat = "Average", label = "Read" }],
            ["AWS/EC2", "EBSWriteBytes", "InstanceId", aws_instance.this.id, { stat = "Average", label = "Write" }]
          ]
        }
      },
      {
        type = "metric", x = 0, y = 7, width = 8, height = 6,
        properties = {
          title  = "Status checks (0 = healthy)",
          view   = "timeSeries", region = var.region, period = 60, stat = "Maximum",
          metrics = [
            ["AWS/EC2", "StatusCheckFailed", "InstanceId", aws_instance.this.id, { label = "Any" }],
            ["AWS/EC2", "StatusCheckFailed_Instance", "InstanceId", aws_instance.this.id, { label = "Instance" }],
            ["AWS/EC2", "StatusCheckFailed_System", "InstanceId", aws_instance.this.id, { label = "System" }]
          ]
        }
      },
      {
        type = "alarm", x = 8, y = 7, width = 8, height = 6,
        properties = {
          title  = "Alarms",
          alarms = [aws_cloudwatch_metric_alarm.cpu_high.arn, aws_cloudwatch_metric_alarm.status_check.arn]
        }
      },
      {
        type = "log", x = 16, y = 7, width = 8, height = 6,
        properties = {
          title  = "Chat requests / 5 min",
          view   = "bar", region = var.region,
          query  = "SOURCE '/chatagent/app' | filter @message like /POST \\/api\\/chat/ | stats count() as requests by bin(5m)"
        }
      },
      {
        type = "log", x = 0, y = 13, width = 24, height = 9,
        properties = {
          title  = "Recent app + llama logs",
          view   = "table", region = var.region,
          query  = "SOURCE '/chatagent/app' | fields @timestamp, @logStream, @message | sort @timestamp desc | limit 100"
        }
      }
    ]
  })
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
