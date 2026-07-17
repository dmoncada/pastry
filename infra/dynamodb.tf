# Single-table design (see spec.md). On-demand billing; native TTL on `ttl`.

resource "aws_dynamodb_table" "pastry" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  attribute {
    name = "GSI1PK"
    type = "S"
  }

  # Resolve public share links: SLUG#<slug> -> the paste item.
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "GSI1PK"
    projection_type = "ALL"
  }

  # Auto-expire device codes, refresh tokens, and pastes with an expiry set.
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }
}
