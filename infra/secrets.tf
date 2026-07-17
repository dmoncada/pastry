# Secrets live in SSM Parameter Store (SecureString). Values come from TF_VAR_* in CI,
# never the repo. The Lambda is also granted ssm:GetParameter on these so it can migrate
# to runtime fetch later; for the MVP the values are passed as Lambda env vars (compute.tf).

resource "aws_ssm_parameter" "jwt_signing_key" {
  name  = "/${local.name}/jwt-signing-key"
  type  = "SecureString"
  value = var.jwt_signing_key
}

resource "aws_ssm_parameter" "github_client_secret" {
  name  = "/${local.name}/github-oauth-client-secret"
  type  = "SecureString"
  value = var.github_oauth_client_secret
}
