# ============================================================
# データ層: DynamoDB / アーカイブS3 / ECR / SSMパラメータ
# ============================================================

# ---- DynamoDB: テーマ下書き（t_draft の移行先） ----

resource "aws_dynamodb_table" "drafts" {
  name         = "polisjapan-drafts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "N"
  }

  attribute {
    name = "post_status"
    type = "N"
  }

  global_secondary_index {
    name            = "post_status-index"
    hash_key        = "post_status"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }
}

# ---- S3: アーカイブバケット（MySQL全量ダンプ・Server/一式の保全先） ----

resource "aws_s3_bucket" "archive" {
  bucket = "polisjapan-archive"
}

resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "archive" {
  bucket                  = aws_s3_bucket.archive.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    id     = "to-glacier-ir"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
  }
}

# ---- ECR: Lambdaコンテナイメージ ----

resource "aws_ecr_repository" "api" {
  name = "polisjapan-api"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "batch_create" {
  name = "polisjapan-batch-create"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "keep_last_5" {
  for_each   = { api = aws_ecr_repository.api.name, batch_create = aws_ecr_repository.batch_create.name }
  repository = each.value

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "直近5イメージのみ保持"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ---- SSM Parameter Store: シークレットの器 ----
# 値はTerraformに書かず、apply後に手動投入する:
#   aws ssm put-parameter --name /polisjapan/openai-api-key --type SecureString --value '...' --overwrite --profile terraform
# ignore_changes[value] により、手動投入した値をTerraformが上書きすることはない

locals {
  secret_names = [
    "openai-api-key",
    "langsmith-api-key",
    "batch-access-key",
    "user-access-key",
    "encrypt-salt",
    "polis-login-user",
    "polis-login-password",
  ]
}

resource "aws_ssm_parameter" "secrets" {
  for_each = toset(local.secret_names)

  name  = "/polisjapan/${each.value}"
  type  = "SecureString"
  value = "CHANGEME"

  lifecycle {
    ignore_changes = [value]
  }
}
