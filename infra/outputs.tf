output "table_name" {
  value = aws_dynamodb_table.pastry.name
}

output "api_url" {
  description = "Invoke URL for the HTTP API (set as the web app's VITE_API_URL)."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "frontend_bucket" {
  description = "S3 bucket the Vite build is synced to."
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "For cache invalidation after a frontend deploy."
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_url" {
  value = local.frontend_url
}

output "github_actions_role_arn" {
  description = "Role ARN for GitHub Actions to assume via OIDC."
  value       = aws_iam_role.github_actions.arn
}
