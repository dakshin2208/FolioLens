# Deploying FolioLens on one AWS server

FolioLens runs on **one EC2 server** in Mumbai (`ap-south-1`): Caddy (HTTPS), the React app, the API,
the background worker, Redis and PostgreSQL, all in Docker. Uploaded statements and nightly database
backups go to a **private S3 bucket**. Secrets live in **SSM Parameter Store**, and the server reads them
through an **IAM role**, so no AWS keys are stored anywhere. The site gets a free HTTPS address,
`<your-ip>.sslip.io`, until you add your own domain.

```
Internet ──443──▶ EC2 (t4g.small)
                   ├─ caddy ─▶ web (nginx + React) ─▶ api (FastAPI) ─▶ db (PostgreSQL)
                   │                                      └─▶ redis ◀─ worker
                   └─ IAM role ─▶ S3 (uploads/ 1 day, backups/ 30 days) · SSM (secrets)
```

You run every command below yourself in **AWS CloudShell** (the `>_` icon in the AWS console, top
bar), which is already signed in as you. It takes about 30–45 minutes the first time.

> **Cost:** new AWS accounts get credits and a 6-month free plan. After that, expect roughly the price of
> one t4g.small instance, a 20 GB disk and one public IPv4 address per month. Check the
> [AWS Pricing Calculator](https://calculator.aws/) for today's prices, and create the budget alarm in
> step 0 **first**.

## 0. Account safety

1. Sign in as root once: **turn on MFA** for root, then create an IAM Identity Center or IAM admin user with
   MFA and use that from now on.
2. **Billing and Cost Management → Budgets → Create budget → Monthly cost budget**, for example $10,
   with email alerts at 50%, 80% and 100%.
3. Switch the console region (top right) to **Asia Pacific (Mumbai) ap-south-1**.

## 1. Open CloudShell and set names

```bash
export AWS_REGION=ap-south-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BUCKET=foliolens-$ACCOUNT_ID          # bucket names must be unique worldwide
echo "$ACCOUNT_ID $BUCKET"
```

## 2. Private S3 bucket

```bash
aws s3api create-bucket --bucket $BUCKET --region $AWS_REGION \
  --create-bucket-configuration LocationConstraint=$AWS_REGION
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket $BUCKET --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-lifecycle-configuration --bucket $BUCKET --lifecycle-configuration '{"Rules":[
  {"ID":"uploads-safety-net","Status":"Enabled","Filter":{"Prefix":"uploads/"},"Expiration":{"Days":1}},
  {"ID":"backups-30-days","Status":"Enabled","Filter":{"Prefix":"backups/"},"Expiration":{"Days":30}}]}'
```

The app deletes each statement right after reading it; the 1-day rule is only a safety net.

## 3. Secrets in SSM Parameter Store

```bash
put() { aws ssm put-parameter --region $AWS_REGION --type SecureString --overwrite \
          --name "/foliolens/prod/$1" --value "$2" > /dev/null && echo "saved $1"; }
put JWT_SECRET        "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
put POSTGRES_PASSWORD "$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
put S3_BUCKET         "$BUCKET"
```

**AI explanations.** Get an API key from your provider's console and **set a monthly spending limit there
first**: the site is public, and every report someone builds makes one or two AI calls. Then:

```bash
put LLM_PROVIDER anthropic                 # or: openai
read -rs -p "Paste your API key (hidden): " KEY; echo; put LLM_API_KEY "$KEY"; unset KEY
read -r  -p "Model ID from your provider's docs: " MODEL; put LLM_MODEL "$MODEL"
```

`read -s` keeps the key off the screen and out of the shell history. To switch AI off later, run
`put LLM_PROVIDER none` and run the update in step 9.

## 4. IAM role for the server

```bash
cat > trust.json <<'JSON'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}
JSON
curl -fsSL https://raw.githubusercontent.com/dakshin2208/FolioLens/main/deploy/iam-policy-single.json \
  | sed "s/BUCKET_NAME/$BUCKET/g; s/ACCOUNT_ID/$ACCOUNT_ID/g" > policy.json

aws iam create-role --role-name foliolens-ec2 --assume-role-policy-document file://trust.json
aws iam put-role-policy --role-name foliolens-ec2 --policy-name foliolens-app --policy-document file://policy.json
aws iam attach-role-policy --role-name foliolens-ec2 \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam create-instance-profile --instance-profile-name foliolens-ec2
aws iam add-role-to-instance-profile --instance-profile-name foliolens-ec2 --role-name foliolens-ec2
```

The role can only read and write `uploads/` and `backups/` in this bucket and read `/foliolens/prod/*`
secrets. `AmazonSSMManagedInstanceCore` lets you open a terminal on the server from the browser, so
no SSH port or key is needed.

## 5. Firewall (security group)

```bash
VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 create-security-group --group-name foliolens-web --description "FolioLens: HTTP and HTTPS only" \
       --vpc-id $VPC --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 80  --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 443 --cidr 0.0.0.0/0
echo $SG
```

Port 22 (SSH) stays closed. Port 80 is needed for the HTTPS certificate and redirects to 443.

## 6. Launch the server

```bash
curl -fsSL https://raw.githubusercontent.com/dakshin2208/FolioLens/main/deploy/ec2-user-data.sh > user-data.sh
AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 \
        --query Parameter.Value --output text)
IID=$(aws ec2 run-instances --image-id $AMI --instance-type t4g.small \
  --iam-instance-profile Name=foliolens-ec2 --security-group-ids $SG \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true}' \
  --metadata-options HttpTokens=required,HttpPutResponseHopLimit=2,HttpEndpoint=enabled \
  --user-data file://user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=foliolens}]' \
  --query 'Instances[0].InstanceId' --output text)
echo $IID
```

`HttpPutResponseHopLimit=2` lets the app inside Docker use the server's IAM role (with the default of
1, boto3 in a container cannot get credentials).

## 7. Fixed public address (Elastic IP)

```bash
aws ec2 wait instance-running --instance-ids $IID
ALLOC=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
aws ec2 associate-address --instance-id $IID --allocation-id $ALLOC
aws ec2 describe-addresses --allocation-ids $ALLOC --query 'Addresses[0].PublicIp' --output text
```

Your site will be `https://<that IP with dashes>.sslip.io`, for example `13-233-10-5.sslip.io`.

## 8. Install FolioLens on the server

Wait 3–4 minutes for the launch script to finish, then **EC2 → Instances → foliolens → Connect →
Session Manager → Connect**. In that browser terminal:

```bash
sudo su - ec2-user
cd /opt/foliolens
git clone https://github.com/dakshin2208/FolioLens.git .
./deploy/setup.sh
```

The first build takes about 10 minutes on a t4g.small. When it ends it prints your address. Open:

- `https://<ip>.sslip.io/demo`: the sample report, no sign-in
- `https://<ip>.sslip.io/register`: create your own advisor account
- `https://<ip>.sslip.io/api/v1/health`: should show `{"status":"ok"}`

The site shows a banner asking visitors to upload only sample statements. Test with
`06_synthetic_cas.pdf` (password `ABCDE1234F`). The site has synthetic market data only, so a real CAS
would not match any fund.

## 9. Updating after you push new code

Session Manager → `sudo su - ec2-user` →

```bash
cd /opt/foliolens && git pull && ./deploy/setup.sh
```

Migrations run automatically when the API starts. Existing reports show an **Update report** button
when the engine version changes.

## 10. Backups, logs and checks

- **Backups:** `deploy/backup.sh` runs every night at 02:15 IST and stores `backups/foliolens-<time>.sql.gz`
  in the bucket for 30 days. Run it by hand any time with `./deploy/backup.sh`.
- **Restore:**
  `aws s3 cp s3://<bucket>/backups/<file>.sql.gz - | gunzip | docker compose -f deploy/docker-compose.single.yml --env-file .env exec -T db psql -U foliolens foliolens`
- **Logs:** `docker compose -f deploy/docker-compose.single.yml --env-file .env logs -f api` (logs rotate at 3 × 10 MB per container).
- **Cron log:** `/var/tmp/foliolens-cron.log`.
- **Uptime:** add a free uptime monitor (for example UptimeRobot) on `/api/v1/health`.

## 11. Using your own domain later

Add an `A` record for your domain pointing to the Elastic IP, then in CloudShell:
`aws ssm put-parameter --type SecureString --overwrite --name /foliolens/prod/DOMAIN --value foliolens.yourdomain.com`
and run the update in step 9. Caddy fetches the new certificate by itself.

## 12. Stopping costs

Stopping the instance stops the instance charge, but the disk and Elastic IP still cost a little. To remove
everything: terminate the instance, release the Elastic IP, empty and delete the bucket, delete the
`/foliolens/prod/*` parameters, the security group and the `foliolens-ec2` role.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `SSM parameter … is missing` | Re-run the `put` line from step 3 for that name |
| `Unable to locate credentials` in the api logs | The hop limit is 1: `aws ec2 modify-instance-metadata-options --instance-id $IID --http-put-response-hop-limit 2 --http-tokens required` |
| Browser shows a certificate error for a few minutes | Caddy is still getting the certificate; check that ports 80 and 443 are open and wait 1–2 minutes |
| Build stops with `Killed` | Memory: check the swap exists with `free -h` (the launch script makes 2 GB) |
| `permission denied … docker.sock` | You are `ssm-user`: run `sudo su - ec2-user` first |
