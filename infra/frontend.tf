# Static frontend: private S3 bucket served through CloudFront via Origin Access Control.

resource "aws_s3_bucket" "frontend" {
  bucket = "${local.name}-frontend-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name}-frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Rewrite browser navigations to the SPA entrypoint before S3 is consulted. Unlike a
# distribution-wide 404 fallback, this leaves API and raw-text misses as actual 404s.
resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${local.name}-spa-rewrite"
  runtime = "cloudfront-js-1.0"
  comment = "Serve the SPA for browser deep links without masking API responses"
  publish = true
  code    = <<-JS
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      var accept = request.headers.accept && request.headers.accept.value || "";

      // Ordered API/raw behaviours bypass this function, but retain this guard for
      // exact namespace roots handled by the default behaviour.
      if (uri === "/api" || uri.indexOf("/api/") === 0 ||
          uri === "/raw" || uri.indexOf("/raw/") === 0) {
        return request;
      }

      // Files (including Vite's /assets/* output) are always served directly.
      if (uri.indexOf(".") !== -1 || uri.indexOf("/assets/") === 0) {
        return request;
      }

      if (accept.indexOf("text/html") !== -1) {
        request.uri = "/index.html";
      }
      return request;
    }
  JS
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  aliases             = local.use_domain ? [var.domain_name] : []

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # The HTTP API, fronted by the same CloudFront domain so the SPA and API are same-origin
  # (the refresh cookie is then first-party). api_endpoint is a full URL; the custom origin
  # wants the bare host.
  origin {
    domain_name = replace(aws_apigatewayv2_api.http.api_endpoint, "https://", "")
    origin_id   = "api-gateway"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    # AWS managed "CachingOptimized" policy.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  # Route the API under /api to API Gateway. The app serves these paths itself (see main.py),
  # so nothing is stripped. Caching is disabled and all viewer headers/cookies/query are
  # forwarded (except Host, which API Gateway supplies), so Authorization and the refresh
  # cookie pass through and responses are never cached.
  ordered_cache_behavior {
    path_pattern             = "/api/*"
    target_origin_id         = "api-gateway"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac" # Managed-AllViewerExceptHostHeader
  }

  # Raw public text is a separate, non-cached API Gateway behavior.
  ordered_cache_behavior {
    path_pattern             = "/raw/*"
    target_origin_id         = "api-gateway"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac" # Managed-AllViewerExceptHostHeader
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = local.use_domain ? null : true
    acm_certificate_arn            = local.use_domain ? aws_acm_certificate.frontend[0].arn : null
    ssl_support_method             = local.use_domain ? "sni-only" : null
    minimum_protocol_version       = local.use_domain ? "TLSv1.2_2021" : null
  }

  # Attaching an unissued certificate fails; wait until its Cloudflare DNS
  # validation record has made it available in ACM.
  depends_on = [aws_acm_certificate_validation.frontend]
}

# Allow only this CloudFront distribution (via OAC) to read the bucket.
data "aws_iam_policy_document" "frontend_bucket" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket.json
}
