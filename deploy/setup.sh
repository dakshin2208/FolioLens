#!/bin/bash
# One-time setup and every later update, on the EC2 server:
#   cd /opt/foliolens && ./deploy/setup.sh
# 1. Reads the secrets from SSM Parameter Store (through the instance's IAM role) into .env
# 2. Works out the web address: the DOMAIN parameter, or <public-ip>.sslip.io if there is none
# 3. Builds and starts the containers, loads the sample market data, installs the cron jobs
set -euo pipefail
cd "$(dirname "$0")/.."
REGION="${AWS_REGION:-ap-south-1}"
P="/foliolens/prod"
COMPOSE="docker compose -f deploy/docker-compose.single.yml"

get() { aws ssm get-parameter --region "$REGION" --name "$P/$1" --with-decryption \
          --query Parameter.Value --output text 2>/dev/null || true; }
need() { v="$(get "$1")"; [ -n "$v" ] || { echo "ERROR: SSM parameter $P/$1 is missing. See docs/DEPLOY_AWS_SINGLE.md step 4." >&2; exit 1; }; echo "$v"; }

# IMDSv2 token, then the instance's public IPv4 (the Elastic IP once attached)
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
DOMAIN="$(get DOMAIN)"
[ -n "$DOMAIN" ] || DOMAIN="${IP//./-}.sslip.io"

JWT_SECRET="$(need JWT_SECRET)"
POSTGRES_PASSWORD="$(need POSTGRES_PASSWORD)"
S3_BUCKET="$(need S3_BUCKET)"
LLM_PROVIDER="$(get LLM_PROVIDER)"; LLM_PROVIDER="${LLM_PROVIDER:-none}"
LLM_API_KEY="$(get LLM_API_KEY)"
LLM_MODEL="$(get LLM_MODEL)"

umask 077
cat > .env <<ENV
ENVIRONMENT=production
JWT_SECRET=$JWT_SECRET
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
DATABASE_URL=postgresql+psycopg://foliolens:$POSTGRES_PASSWORD@db:5432/foliolens
CORS_ORIGINS=["https://$DOMAIN"]
STORAGE_BACKEND=s3
S3_BUCKET=$S3_BUCKET
AWS_DEFAULT_REGION=$REGION
BENCHMARK_SYMBOL=NIFTY50TRI
LLM_PROVIDER=$LLM_PROVIDER
LLM_API_KEY=$LLM_API_KEY
LLM_MODEL=$LLM_MODEL
DOMAIN=$DOMAIN
DEMO_NOTICE=Demo site: please upload only sample or synthetic statements, never a real client's.
ENV
echo "Wrote .env (only readable by you) for https://$DOMAIN"

# Compose reads POSTGRES_PASSWORD, DOMAIN and DEMO_NOTICE from .env in the project directory
$COMPOSE --env-file .env up -d --build --wait
$COMPOSE --env-file .env exec -T api python -m app.market_data.cli seed-demo

# Cron: delete leftover upload files hourly; back up the database to S3 every night at 02:15 IST
CRON_FILE=$(mktemp)
crontab -l 2>/dev/null | grep -v "foliolens" > "$CRON_FILE" || true
cat >> "$CRON_FILE" <<CRON
0 * * * * cd /opt/foliolens && $COMPOSE --env-file .env exec -T api python -m app.jobs.cleanup >> /var/tmp/foliolens-cron.log 2>&1 # foliolens
45 20 * * * cd /opt/foliolens && ./deploy/backup.sh >> /var/tmp/foliolens-cron.log 2>&1 # foliolens
CRON
crontab "$CRON_FILE" && rm -f "$CRON_FILE"

echo
echo "FolioLens is running:  https://$DOMAIN"
echo "Sample report:         https://$DOMAIN/demo"
echo "Health check:          https://$DOMAIN/api/v1/health"
