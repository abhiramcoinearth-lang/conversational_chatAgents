output "instance_id" {
  value = aws_instance.this.id
}

output "instance_public_ip" {
  description = "Elastic IP — create a DNS A-record: chat.chatbucket.chat -> this"
  value       = aws_eip.this.public_ip
}

output "ssh_command" {
  value = "ssh -i ${path.module}/chatagent-key.pem ubuntu@${aws_eip.this.public_ip}"
}

output "app_url_ip" {
  description = "Reachable immediately over HTTP by IP (before DNS)"
  value       = "http://${aws_eip.this.public_ip}/health"
}

output "app_url_domain" {
  description = "HTTPS URL once the DNS A-record exists"
  value       = "https://${var.domain}/"
}

output "ssh_private_key" {
  description = "Private key for the CI/CD SSH_PRIVATE_KEY secret"
  value       = tls_private_key.ssh.private_key_pem
  sensitive   = true
}
