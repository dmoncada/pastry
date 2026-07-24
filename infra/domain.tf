# Cloudflare validates the ACM certificate and resolves the frontend hostname to
# the CloudFront distribution.
data "cloudflare_zone" "frontend" {
  count = local.use_domain ? 1 : 0

  filter = {
    name = var.cloudflare_zone_name
  }
}

# CloudFront only accepts ACM certificates issued in us-east-1.
resource "aws_acm_certificate" "frontend" {
  count    = local.use_domain ? 1 : 0
  provider = aws.us_east_1

  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  # The existing deploy role can update its inline policy. Ensure that update adds
  # ACM access before this first certificate-creation call.
  depends_on = [aws_iam_role_policy.github_deploy]
}

resource "cloudflare_dns_record" "certificate_validation" {
  for_each = local.use_domain ? {
    for option in aws_acm_certificate.frontend[0].domain_validation_options : option.domain_name => {
      name    = option.resource_record_name
      type    = option.resource_record_type
      content = option.resource_record_value
    }
  } : {}

  zone_id = data.cloudflare_zone.frontend[0].id
  name    = each.value.name
  type    = each.value.type
  content = each.value.content
  ttl     = 1
  proxied = false
}

resource "aws_acm_certificate_validation" "frontend" {
  count    = local.use_domain ? 1 : 0
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.frontend[0].arn
  validation_record_fqdns = [for record in cloudflare_dns_record.certificate_validation : record.name]
}

resource "cloudflare_dns_record" "frontend" {
  count = local.use_domain ? 1 : 0

  zone_id = data.cloudflare_zone.frontend[0].id
  name    = var.domain_name
  type    = "CNAME"
  content = aws_cloudfront_distribution.frontend.domain_name
  ttl     = 1
  proxied = false
  comment = "Pastry CloudFront distribution"
}
