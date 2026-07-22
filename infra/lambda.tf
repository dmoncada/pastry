# FastAPI (via Mangum) packaged as a zip Lambda. Build with scripts/build-lambda.sh first.

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  # Single-table access, including the GSI.
  statement {
    sid = "DynamoDB"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]
    resources = [
      aws_dynamodb_table.pastry.arn,
      "${aws_dynamodb_table.pastry.arn}/index/*",
    ]
  }

  # Read the secrets (for future runtime fetch).
  statement {
    sid       = "SSMRead"
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = [aws_ssm_parameter.jwt_signing_key.arn, aws_ssm_parameter.github_client_secret.arn]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name}-api"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name}-api"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "pastry_api.main.handler"
  filename      = local.lambda_zip
  # Ensures redeploy when the artifact changes. Guarded so `tofu validate` works before the
  # zip is built; plan/apply (and CI, which builds first) still hash the real artifact.
  source_code_hash = fileexists(local.lambda_zip) ? filebase64sha256(local.lambda_zip) : null
  memory_size      = 256
  timeout          = 15

  environment {
    variables = {
      PASTRY_TABLE_NAME          = aws_dynamodb_table.pastry.name
      PASTRY_AUTH_MODE           = var.auth_mode
      PASTRY_CORS_ORIGINS        = jsonencode([local.frontend_url])
      PASTRY_COOKIE_SECURE       = "true" # HTTPS-only refresh cookie in prod
      PASTRY_JWT_SIGNING_KEY     = aws_ssm_parameter.jwt_signing_key.value
      GITHUB_OAUTH_CLIENT_ID     = var.github_oauth_client_id
      GITHUB_OAUTH_CLIENT_SECRET = aws_ssm_parameter.github_client_secret.value
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]
}
