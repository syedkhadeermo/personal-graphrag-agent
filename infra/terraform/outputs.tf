output "instance_id" {
  description = "EC2 instance ID used with AWS Systems Manager Session Manager."
  value       = aws_instance.api.id
}

output "public_ip" {
  description = "Ephemeral public IPv4 address of the API host."
  value       = aws_instance.api.public_ip
}

output "health_url" {
  description = "Public health endpoint, restricted by the security group."
  value       = "http://${aws_instance.api.public_ip}:8000/health"
}

output "capabilities_url" {
  description = "Public capability endpoint, restricted by the security group."
  value       = "http://${aws_instance.api.public_ip}:8000/capabilities"
}

output "artifact_bucket" {
  description = "Private S3 bucket receiving synchronized runtime artifacts."
  value       = aws_s3_bucket.artifacts.id
}

output "session_manager_command" {
  description = "Administrative shell command; inbound SSH remains closed."
  value       = "aws ssm start-session --target ${aws_instance.api.id} --profile terraform-admin --region ${var.aws_region}"
}
