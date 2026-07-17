data "aws_caller_identity" "current" {}

locals {
  name       = var.project
  lambda_zip = var.lambda_zip_path != "" ? var.lambda_zip_path : "${path.module}/../build/lambda.zip"
  use_domain = var.domain_name != ""
  # The browser origin the API must allow, and the frontend's public URL.
  frontend_url = local.use_domain ? "https://${var.domain_name}" : "https://${aws_cloudfront_distribution.frontend.domain_name}"
}
