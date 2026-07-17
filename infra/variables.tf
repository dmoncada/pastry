variable "region" {
  type    = string
  default = "us-west-2"
}

variable "project" {
  type    = string
  default = "pastry"
}

variable "table_name" {
  type    = string
  default = "pastry"
}

# Optional custom domain for the frontend (CloudFront). Empty = use the CloudFront domain.
variable "domain_name" {
  type    = string
  default = ""
}

# ACM certificate ARN for domain_name. MUST be in us-east-1 (CloudFront requirement).
variable "acm_certificate_arn" {
  type    = string
  default = ""
}

# Path to the packaged Lambda zip (built by scripts/build-lambda.sh). Empty = default path.
variable "lambda_zip_path" {
  type    = string
  default = ""
}

# GitHub repo (owner/name) allowed to assume the CI deploy role via OIDC.
variable "github_repo" {
  type    = string
  default = "your-org/pastry"
}

variable "auth_mode" {
  type    = string
  default = "github"
}

# --- Secrets (provide via TF_VAR_* from CI; never commit) ---

variable "jwt_signing_key" {
  type      = string
  sensitive = true
  default   = "change-me-in-ci"
}

variable "github_oauth_client_id" {
  type    = string
  default = ""
}

variable "github_oauth_client_secret" {
  type      = string
  sensitive = true
  default   = ""
}
