# AWS deployment

## Prerequisites

- Python 3.9+
- Docker (for building and pushing images)
- AWS CLI optional; credentials can be provided interactively or via file

Install dependencies:

```bash
pip install boto3
```

## Credentials

The script uses AWS credentials in this order:

1. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optionally `AWS_SESSION_TOKEN` and `AWS_DEFAULT_REGION`
2. Credentials file: `.aws-deploy-credentials` in the repo root (gitignored). Format: one `KEY=value` per line
3. Interactive prompt: you will be asked for access key and secret key

Do not commit credentials to the repo.

## Deploy

From the repo root:

```bash
# Full deploy: provision CloudFormation stack (VPC, RDS, ECR, ECS, ALBs), build/push images, create task definitions and ECS services
python scripts/aws_deploy.py --region us-east-1

# Skip infra (use existing stack), only build/push and update ECS
python scripts/aws_deploy.py --no-provision --region us-east-1

# Skip Docker build/push (use existing ECR images)
python scripts/aws_deploy.py --no-provision --skip-build
```

First run will prompt for a DB password (for RDS) if `POSTGRES_PASSWORD` is not set in `backend/.env`.

## Env variables

All variables from `backend/.env` and `backend/services/<service>/.env` (or `.env.example`) are collected and stored in AWS Secrets Manager per service. Endpoint URLs are overwritten for AWS (RDS host, internal service discovery URLs, public ALB URLs for portal and gateway).

## Output

After deployment, the script prints the public **Frontend** (Next.js portal UI), **Portal API**, and **Gateway** URLs and writes `extension/config.aws.js` with the portal and gateway URLs for the extension.

## Frontend

The portal frontend (Next.js) is built with `NEXT_PUBLIC_API_URL` set to the Portal ALB URL so it talks to the Django backend. It runs on ECS behind the Frontend ALB (port 3000). If you added frontend to an existing stack, run a full deploy once (without `--no-provision`) so CloudFormation creates the Frontend ALB, target group, and ECR repo.
