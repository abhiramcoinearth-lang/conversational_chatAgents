# ------------------------------------------------------------------------------
# ECR: AWS-native container registry for the app image. CI pushes here (via
# GitHub OIDC, no static keys); the EC2 instance pulls via its IAM role.
# ------------------------------------------------------------------------------
resource "aws_ecr_repository" "app" {
  name                 = "conversational-chatagents"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep the registry tidy: retain only the most recent images.
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 15 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 15
      }
      action = { type = "expire" }
    }]
  })
}

# --- GitHub Actions OIDC role (CI assumes this to push to ECR) ----------------
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "gha_ecr" {
  name = "chatagent-gha-ecr"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          # Only the main branch of this repo may assume the role (not PRs/other refs).
          "token.actions.githubusercontent.com:sub" = "repo:abhiramcoinearth-lang/conversational_chatAgents:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "gha_ecr" {
  name = "ecr-push"
  role = aws_iam_role.gha_ecr.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Resource = aws_ecr_repository.app.arn
      }
    ]
  })
}

# Let the EC2 instance pull from ECR using its instance-profile role.
resource "aws_iam_role_policy_attachment" "ec2_ecr_read" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "gha_ecr_role_arn" {
  description = "Set as the role-to-assume in the deploy workflow"
  value       = aws_iam_role.gha_ecr.arn
}
