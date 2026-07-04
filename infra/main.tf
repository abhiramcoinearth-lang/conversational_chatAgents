data "aws_vpc" "default" {
  default = true
}

# Latest Deep Learning Base GPU AMI (Ubuntu 22.04): NVIDIA driver + Docker +
# nvidia-container-toolkit preinstalled.
data "aws_ami" "dlami" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*"]
  }
  filter {
    name   = "state"
    values = ["available"]
  }
}

# --- SSH key pair (generated locally, saved to disk for admin + CI/CD) --------
resource "tls_private_key" "ssh" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "this" {
  key_name   = "chatagent-key"
  public_key = tls_private_key.ssh.public_key_openssh
}

resource "local_sensitive_file" "private_key" {
  content         = tls_private_key.ssh.private_key_pem
  filename        = "${path.module}/chatagent-key.pem"
  file_permission = "0600"
}

# --- Security group ----------------------------------------------------------
resource "aws_security_group" "this" {
  name        = "chatagent-sg"
  description = "Chat Agent Platform: HTTP/HTTPS + SSH"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "chatagent-sg" }
}

# --- IAM role (SSM access + CloudWatch agent) --------------------------------
resource "aws_iam_role" "ec2" {
  name = "chatagent-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cw" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "this" {
  name = "chatagent-instance-profile"
  role = aws_iam_role.ec2.name
}

# --- EC2 instance ------------------------------------------------------------
resource "aws_instance" "this" {
  ami                    = data.aws_ami.dlami.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.this.key_name
  vpc_security_group_ids = [aws_security_group.this.id]
  iam_instance_profile   = aws_iam_instance_profile.this.name

  root_block_device {
    volume_size = var.root_volume_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url    = var.repo_url
    llama_model = var.llama_model
    llama_ctx   = var.llama_ctx
    domain      = var.domain
    region      = var.region
  })

  # user_data provisions a FRESH instance only; the running box is updated via
  # CI/CD (compose files), so ignore user_data drift to avoid replacing a live,
  # stateful instance. Delete this ignore_changes to force a rebuild from scratch.
  lifecycle {
    ignore_changes = [user_data]
  }

  tags = { Name = "conversational-chatagents" }
}

resource "aws_eip" "this" {
  instance = aws_instance.this.id
  domain   = "vpc"
  tags     = { Name = "chatagent-eip" }
}
