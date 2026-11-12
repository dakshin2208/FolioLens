#!/bin/bash
# Nightly PostgreSQL backup to the private S3 bucket (kept 30 days by the bucket's lifecycle rule).
# Restore: aws s3 cp s3://<bucket>/backups/<file>.sql.gz - | gunzip | \
#          docker compose -f deploy/docker-compose.single.yml --env-file .env exec -T db psql -U foliolens foliolens
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
STAMP=$(date -u +%Y%m%d-%H%M%S)
docker compose -f deploy/docker-compose.single.yml --env-file .env exec -T db \
  pg_dump -U foliolens --no-owner foliolens | gzip \
  | aws s3 cp - "s3://$S3_BUCKET/backups/foliolens-$STAMP.sql.gz" --sse AES256 --region "$AWS_DEFAULT_REGION"
echo "$(date -u) backup ok: backups/foliolens-$STAMP.sql.gz"
