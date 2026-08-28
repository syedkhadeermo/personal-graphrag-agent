resource "aws_instance" "api" {
  ami                         = data.aws_ssm_parameter.amazon_linux_2023.value
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.api.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.ec2.name

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    app_repository_url   = var.app_repository_url
    app_git_ref          = var.app_git_ref
    artifact_bucket_name = aws_s3_bucket.artifacts.id
  })

  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 20
  }

  lifecycle {
    precondition {
      condition     = var.allowed_api_cidr != "0.0.0.0/0"
      error_message = "The API must not be exposed to the entire internet."
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-api"
  }

  depends_on = [
    aws_internet_gateway.main,
    aws_route_table_association.public,
    aws_iam_role_policy.artifacts,
    aws_iam_role_policy_attachment.ssm,
  ]
}
