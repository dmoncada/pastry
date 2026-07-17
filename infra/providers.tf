# Main stack providers + remote state backend.
# Fill the backend "s3" values from the bootstrap stack's outputs, then `tofu init`.

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Pinned to v5: v6 emits a premature "hash_key is deprecated, use key_schema"
      # warning for the table's primary key, but v6.55 has no top-level key_schema
      # argument yet — so there is no working replacement. Revisit v6 once it lands.
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # bucket         = "<state_bucket from bootstrap>"
    # key            = "pastry/main.tfstate"
    # region         = "us-west-2"
    # dynamodb_table = "pastry-tofu-lock"
    # encrypt        = true
  }
}

provider "aws" {
  region = var.region
}

# CloudFront + ACM for the frontend must live in us-east-1 (AWS requirement).
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
