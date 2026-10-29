#!/bin/sh
# Builds /opt/foliolens/.env from SSM Parameter Store using the EC2 instance's IAM role.
# Secrets never live in the repository or in shell history.
set -eu
REGION="${AWS_REGION:-ap-south-1}"
P="/foliolens/prod"
get() { aws ssm get-parameter --region "$REGION" --name "$P/$1" --with-decryption \
          --query Parameter.Value --output text; }

umask 077
cat > "$(dirname "$0")/../.env" <<ENV
ENVIRONMENT=production
JWT_SECRET=$(get JWT_SECRET)
DATABASE_URL=$(get DATABASE_URL)
CORS_ORIGINS=["https://$(get DOMAIN)"]
STORAGE_BACKEND=s3
S3_BUCKET=$(get S3_BUCKET)
AWS_DEFAULT_REGION=$REGION
BENCHMARK_SYMBOL=NIFTY50TRI
LLM_PROVIDER=$(get LLM_PROVIDER)
LLM_API_KEY=$(get LLM_API_KEY)
LLM_MODEL=$(get LLM_MODEL)
ENV
echo "Wrote .env (permissions 600)"
