#!/usr/bin/env python3
"""
Deploy HTE stack to AWS: gather .env variables, provision infra (CloudFormation),
build/push images to ECR, create task definitions and ECS services, output extension config.
Prompts for AWS credentials if not in env or credentials file.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add repo root so we can import aws_env_loader
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Install boto3: pip install boto3", file=sys.stderr)
    sys.exit(1)

from scripts.aws_env_loader import (
    ENDPOINT_KEYS,
    SERVICE_NAMES,
    get_env_for_service,
    load_all_env,
)

# Service name -> (container port, ECR repo suffix, build context relative to repo root)
SERVICES: Dict[str, tuple] = {
    "portal": (8000, "portal", "backend"),
    "agent_gateway": (8003, "agent-gateway", "backend/services/agent_gateway"),
    "fact_checking": (8001, "fact-checking", "backend/services/fact_checking"),
    "media_checking": (8007, "media-checking", "backend/services/media_checking"),
    "ai_text_detector": (8002, "ai-text-detector", "backend/services/ai_text_detector"),
    "info_graph": (8004, "info-graph", "backend/services/info_graph"),
    "content_safety": (8005, "content-safety", "backend/services/content_safety"),
    "media_explanation": (8006, "media-explanation", "backend/services/media_explanation"),
    "frontend": (3000, "frontend", "frontend"),
}

ENVIRONMENT_NAME = "hte"


def _load_dotenv_into_environ(path: Path) -> None:
    """Load KEY=VALUE from path into os.environ (skip if key already set)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1].replace("\\n", "\n")
        if key and key not in os.environ:
            os.environ[key] = value


def get_credentials(credentials_file: Optional[Path]) -> Dict[str, str]:
    """Load AWS credentials from env (including .env files), credentials file, or interactive prompt."""
    # Load .env into os.environ so env vars are visible (scripts/.env, repo .env)
    _load_dotenv_into_environ(REPO_ROOT / ".env")
    _load_dotenv_into_environ(REPO_ROOT / "scripts" / ".env")
    creds: Dict[str, str] = {}
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        creds["AWS_ACCESS_KEY_ID"] = os.environ["AWS_ACCESS_KEY_ID"]
        creds["AWS_SECRET_ACCESS_KEY"] = os.environ["AWS_SECRET_ACCESS_KEY"]
        if os.environ.get("AWS_SESSION_TOKEN"):
            creds["AWS_SESSION_TOKEN"] = os.environ["AWS_SESSION_TOKEN"]
        return creds
    if credentials_file and credentials_file.exists():
        text = credentials_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                creds[k.strip()] = v.strip()
        if creds.get("AWS_ACCESS_KEY_ID") and creds.get("AWS_SECRET_ACCESS_KEY"):
            return creds
    # Interactive prompt
    try:
        getpass = __import__("getpass")
    except ImportError:
        getpass = None
    print("AWS credentials not found in environment or file. Enter them (or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY):")
    access = input("AWS_ACCESS_KEY_ID: ").strip()
    secret = (getpass.getpass("AWS_SECRET_ACCESS_KEY: ") if getpass else input("AWS_SECRET_ACCESS_KEY: ")).strip()
    if not access or not secret:
        raise SystemExit("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required.")
    creds["AWS_ACCESS_KEY_ID"] = access
    creds["AWS_SECRET_ACCESS_KEY"] = secret
    return creds


def validate_credentials(region: str, creds: Dict[str, str]) -> None:
    """Validate credentials with STS GetCallerIdentity."""
    session = boto3.Session(
        aws_access_key_id=creds.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=creds.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=creds.get("AWS_SESSION_TOKEN"),
        region_name=region,
    )
    sts = session.client("sts")
    try:
        sts.get_caller_identity()
    except ClientError as e:
        raise SystemExit(f"Invalid AWS credentials: {e}") from e


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    """Run command; raise on non-zero exit."""
    env_ = os.environ.copy()
    if env:
        env_.update(env)
    r = subprocess.run(cmd, cwd=cwd, env=env_, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nstdout: {r.stdout}\nstderr: {r.stderr}")
    return r


def get_stack_outputs(cfn: Any, stack_name: str) -> Dict[str, str]:
    """Get CloudFormation stack outputs as key -> value."""
    try:
        desc = cfn.describe_stacks(StackName=stack_name)
    except ClientError as e:
        if "does not exist" in str(e).lower():
            return {}
        raise
    if not desc.get("Stacks"):
        return {}
    outputs = desc["Stacks"][0].get("Outputs") or []
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def build_endpoint_mapping(outputs: Dict[str, str], namespace: str = "hte.local") -> Dict[str, str]:
    """Build env key -> value for AWS endpoints (RDS, ALB, service discovery)."""
    mapping: Dict[str, str] = {}
    rds = outputs.get("RDSEndpoint") or ""
    if rds:
        mapping["POSTGRES_HOST"] = rds
    portal_url = outputs.get("PortalALBUrl") or ""
    gateway_url = outputs.get("GatewayALBUrl") or ""
    if portal_url:
        mapping["AGENT_GATEWAY_PORTAL_BASE_URL"] = portal_url.rstrip("/")
    # Internal service URLs via Cloud Map: http://<service>.hte.local:<port>
    mapping["AGENT_GATEWAY_AI_TEXT_DETECTOR_URL"] = f"http://ai_text_detector.{namespace}:8002"
    mapping["AGENT_GATEWAY_MEDIA_CHECKING_URL"] = f"http://media_checking.{namespace}:8007"
    mapping["AGENT_GATEWAY_FACT_CHECKING_URL"] = f"http://fact_checking.{namespace}:8001"
    mapping["AGENT_GATEWAY_INFO_GRAPH_URL"] = f"http://info_graph.{namespace}:8004"
    mapping["AGENT_GATEWAY_CONTENT_SAFETY_URL"] = f"http://content_safety.{namespace}:8005"
    mapping["AGENT_GATEWAY_MEDIA_EXPLANATION_URL"] = f"http://media_explanation.{namespace}:8006"
    if gateway_url:
        mapping["GATEWAY_fact_check_base_url"] = f"http://fact_checking.{namespace}:8001"
        mapping["GATEWAY_media_check_base_url"] = f"http://ai_text_detector.{namespace}:8002"
    return mapping


def deploy_cloudformation(
    cfn: Any,
    stack_name: str,
    region: str,
    template_path: Path,
    db_password: str,
    env_name: str,
) -> Dict[str, str]:
    """Create or update CloudFormation stack; return outputs."""
    # #region agent log
    import time
    _log_path = REPO_ROOT / "debug-dc27dc.log"
    try:
        with open(_log_path, "a", encoding="utf-8") as _lf:
            _lf.write(json.dumps({"sessionId": "dc27dc", "runId": "deploy", "hypothesisId": "H1", "location": "aws_deploy.py:deploy_cloudformation", "message": "create_stack args", "data": {"template_path": str(template_path), "stack_name": stack_name, "region": region, "template_exists": template_path.exists()}, "timestamp": int(time.time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion
    with open(template_path, "r", encoding="utf-8") as f:
        body = f.read()
    params = [
        {"ParameterKey": "EnvironmentName", "ParameterValue": env_name},
        {"ParameterKey": "DBPassword", "ParameterValue": db_password},
        {"ParameterKey": "VpcId", "ParameterValue": ""},
    ]
    try:
        cfn.create_stack(
            StackName=stack_name,
            TemplateBody=body,
            Parameters=params,
            Capabilities=["CAPABILITY_NAMED_IAM"],
            OnFailure="ROLLBACK",
        )
        print("Creating stack (this may take several minutes)...")
        waiter = cfn.get_waiter("stack_create_complete")
        waiter.wait(StackName=stack_name)
    except ClientError as e:
        # #region agent log
        try:
            with open(_log_path, "a", encoding="utf-8") as _lf:
                _lf.write(json.dumps({"sessionId": "dc27dc", "runId": "deploy", "hypothesisId": "H2", "location": "aws_deploy.py:deploy_cloudformation", "message": "ClientError", "data": {"code": e.response.get("Error", {}).get("Code"), "message": str(e)}, "timestamp": int(time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion
        if "AlreadyExistsException" not in str(e):
            raise
        # Update
        try:
            cfn.update_stack(
                StackName=stack_name,
                TemplateBody=body,
                Parameters=params,
                Capabilities=["CAPABILITY_NAMED_IAM"],
            )
            print("Updating stack...")
            waiter = cfn.get_waiter("stack_update_complete")
            waiter.wait(StackName=stack_name)
        except ClientError as e2:
            if "No updates" not in str(e2):
                raise
            print("Stack already up to date.")
    return get_stack_outputs(cfn, stack_name)


def put_secret(secrets: Any, secret_name: str, secret_dict: Dict[str, str]) -> str:
    """Create or update secret in Secrets Manager; return ARN."""
    secret_string = json.dumps(secret_dict)
    try:
        r = secrets.create_secret(Name=secret_name, SecretString=secret_string)
        return r["ARN"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceExistsException":
            raise
        secrets.put_secret_value(SecretId=secret_name, SecretString=secret_string)
        r = secrets.describe_secret(SecretId=secret_name)
        return r["ARN"]


def ecr_login(region: str, account_id: str) -> None:
    """Run docker login for ECR."""
    import base64
    ecr = boto3.client("ecr", region_name=region)
    token = ecr.get_authorization_token()
    auth = token["authorizationData"][0]
    user, password = base64.b64decode(auth["authorizationToken"]).decode().split(":", 1)
    registry = auth["proxyEndpoint"].replace("https://", "")
    proc = subprocess.run(
        ["docker", "login", "-u", user, "--password-stdin", registry],
        input=password.encode(),
        capture_output=True,
        text=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ECR login failed: {proc.stderr.decode()}")


def build_and_push(
    repo_root: Path,
    region: str,
    account_id: str,
    env_name: str,
    service_name: str,
    ecr_suffix: str,
    context: str,
    skip_build: bool,
    build_args: Optional[Dict[str, str]] = None,
) -> str:
    """Build Docker image and push to ECR; return image URI."""
    repo_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{env_name}/{ecr_suffix}"
    if skip_build:
        return f"{repo_uri}:latest"
    context_path = repo_root / context
    if not (context_path / "Dockerfile").exists():
        raise FileNotFoundError(f"No Dockerfile in {context_path}")
    # Fargate requires linux/amd64; build for that platform (avoids CannotPullContainerError on ARM hosts)
    build_cmd = ["docker", "build", "--platform", "linux/amd64", "-t", f"{repo_uri}:latest"]
    if build_args:
        for k, v in build_args.items():
            build_cmd.extend(["--build-arg", f"{k}={v}"])
    build_cmd.append(".")
    print(f"Building {service_name} in {context_path} (linux/amd64)...")
    run_cmd(build_cmd, cwd=context_path)
    print(f"Pushing {repo_uri}:latest...")
    run_cmd(["docker", "push", f"{repo_uri}:latest"], cwd=context_path)
    return f"{repo_uri}:latest"


def create_service_discovery_services(
    servicediscovery: Any,
    namespace_id: str,
    service_names: List[str],
    ports: Dict[str, int],
) -> Dict[str, str]:
    """Create Cloud Map service for each backend service; return service_id by name."""
    result = {}
    for name in service_names:
        if name in ("portal", "agent_gateway"):
            continue
        port = ports.get(name, 8000)
        try:
            r = servicediscovery.create_service(
                Name=name,
                NamespaceId=namespace_id,
                DnsConfig={
                    "DnsRecords": [{"Type": "A", "TTL": 10}],
                    "RoutingPolicy": "MULTIVALUE",
                },
                HealthCheckCustomConfig={"FailureThreshold": 1},
            )
            result[name] = r["Service"]["Id"]
        except ClientError as e:
            if "ResourceExistsException" not in str(e) and "AlreadyExists" not in str(e):
                raise
            # Get existing
            list_r = servicediscovery.list_services(Filters=[{"Name": "NAMESPACE_ID", "Values": [namespace_id]}])
            for s in list_r.get("Services", []):
                if s["Name"] == name:
                    result[name] = s["Id"]
                    break
    return result


def register_task_definition(
    ecs: Any,
    env_name: str,
    service_name: str,
    image_uri: str,
    port: int,
    secret_arn: str,
    env_overrides: Dict[str, str],
    execution_role_arn: str,
    task_role_arn: str,
    cpu: int,
    memory: int,
    account_id: str,
    region: str,
) -> str:
    """Register ECS task definition; return family:revision."""
    # Build secrets list from the secret ARN (JSON secret); we pass each key as valueFrom arn:key::
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        sec = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_dict = json.loads(sec["SecretString"])
    except Exception:
        secret_dict = {}
    # ECS forbids the same name in both environment and secrets; exclude env_overrides keys from secrets
    env_override_keys = set(env_overrides.keys())
    secrets_block: List[Dict[str, str]] = []
    for k in secret_dict:
        if k in env_override_keys:
            continue
        value_from = f"{secret_arn}:{k}::"
        secrets_block.append({"name": k, "valueFrom": value_from})
    env_block = [{"name": k, "value": v} for k, v in env_overrides.items()]
    container_name = service_name.replace("_", "-")
    task_family = f"{env_name}-{container_name}"
    td = {
        "family": task_family,
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": str(cpu),
        "memory": str(memory),
        "executionRoleArn": execution_role_arn,
        "taskRoleArn": task_role_arn,
        "containerDefinitions": [
            {
                "name": container_name,
                "image": image_uri,
                "portMappings": [{"containerPort": port, "protocol": "tcp"}],
                "essential": True,
                "environment": env_block,
                "secrets": secrets_block,
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": f"/ecs/{env_name}/{container_name}",
                        "awslogs-region": region,
                        "awslogs-stream-prefix": "ecs",
                    },
                },
            }
        ],
    }
    r = ecs.register_task_definition(**td)
    rev = r["taskDefinition"]["revision"]
    return f"{task_family}:{rev}"


def ensure_log_group(logs: Any, name: str) -> None:
    """Create CloudWatch log group if not exists."""
    try:
        logs.create_log_group(logGroupName=name)
    except ClientError as e:
        if "ResourceAlreadyExistsException" not in str(e):
            raise


def create_ecs_service(
    ecs: Any,
    cluster_name: str,
    service_name: str,
    task_def: str,
    subnet_ids: List[str],
    security_group_ids: List[str],
    target_group_arn: Optional[str],
    container_name: str,
    container_port: int,
    discovery_registry_arn: Optional[str] = None,
) -> None:
    """Create or update ECS service."""
    kwargs = {
        "cluster": cluster_name,
        "serviceName": service_name,
        "taskDefinition": task_def,
        "desiredCount": 1,
        "launchType": "FARGATE",
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": subnet_ids,
                "securityGroups": security_group_ids,
                "assignPublicIp": "DISABLED",
            }
        },
    }
    if target_group_arn:
        kwargs["loadBalancers"] = [
            {
                "targetGroupArn": target_group_arn,
                "containerName": container_name,
                "containerPort": container_port,
            }
        ]
        # Allow tasks time to start before ALB health checks; avoids 503 during deploy
        kwargs["healthCheckGracePeriodSeconds"] = 120
    if discovery_registry_arn:
        # Cloud Map serviceRegistries: do not pass containerPort (AWS rejects it for this registry type)
        kwargs["serviceRegistries"] = [
            {"registryArn": discovery_registry_arn, "containerName": container_name}
        ]
    try:
        ecs.create_service(**kwargs)
        print(f"Created ECS service {service_name}")
    except ClientError as e:
        err_msg = str(e)
        # Service already exists: AWS may return AlreadyExistsException or InvalidParameterException (not idempotent)
        if "AlreadyExistsException" not in err_msg and "not idempotent" not in err_msg:
            raise
        update_kwargs = {
            "cluster": cluster_name,
            "service": service_name,
            "taskDefinition": task_def,
            "desiredCount": 1,
            "forceNewDeployment": True,
        }
        if target_group_arn:
            update_kwargs["healthCheckGracePeriodSeconds"] = 120
        ecs.update_service(**update_kwargs)
        print(f"Updated ECS service {service_name}")


def run_migrate(session: Any, stack_name: str, env_name: str, region: str) -> None:
    """Run Django migrations via a one-off ECS task (portal task definition)."""
    cfn = session.client("cloudformation")
    outputs = get_stack_outputs(cfn, stack_name)
    if not outputs:
        raise SystemExit(f"Stack {stack_name} not found.")
    cluster = outputs.get("ECSClusterName", "").strip()
    subnet_ids = [s.strip() for s in (outputs.get("PrivateSubnetIds") or "").split(",") if s.strip()]
    sg_id = (outputs.get("ECSSecurityGroupId") or "").strip()
    if not cluster or not subnet_ids or not sg_id:
        raise SystemExit("Stack missing ECSClusterName, PrivateSubnetIds, or ECSSecurityGroupId.")
    task_family = f"{env_name}-portal"
    ecs = session.client("ecs")
    resp = ecs.run_task(
        cluster=cluster,
        taskDefinition=task_family,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnet_ids,
                "securityGroups": [sg_id],
                "assignPublicIp": "DISABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "portal",
                    "command": ["python", "manage.py", "migrate", "--noinput"],
                }
            ]
        },
    )
    tasks = resp.get("tasks") or []
    failures = resp.get("failures") or []
    if failures:
        for f in failures:
            print(f"Run task failure: {f.get('reason', '')} {f.get('detail', '')}", file=sys.stderr)
        raise SystemExit(1)
    if not tasks:
        raise SystemExit("No task started.")
    task_arn = tasks[0]["taskArn"]
    print(f"Started migration task: {task_arn}")
    print("Check status: aws ecs describe-tasks --cluster", cluster, "--tasks", task_arn, "--region", region)


def run_init_db(
    session: Any,
    stack_name: str,
    env_name: str,
    region: str,
    db_password: str,
) -> None:
    """Create the application database on RDS via a Lambda (build zip, create/update function, invoke)."""
    cfn = session.client("cloudformation")
    outputs = get_stack_outputs(cfn, stack_name)
    if not outputs:
        raise SystemExit(f"Stack {stack_name} not found.")
    role_arn = (outputs.get("LambdaInitDbRoleArn") or "").strip()
    if not role_arn:
        raise SystemExit(
            "Stack missing LambdaInitDbRoleArn. Update the stack (re-run deploy or update CloudFormation) to add the init_db Lambda role."
        )
    rds_host = (outputs.get("RDSEndpoint") or "").strip()
    rds_port = (outputs.get("RDSPort") or "5432").strip()
    subnet_ids = [s.strip() for s in (outputs.get("PrivateSubnetIds") or "").split(",") if s.strip()]
    sg_id = (outputs.get("ECSSecurityGroupId") or "").strip()
    if not rds_host or not subnet_ids or not sg_id:
        raise SystemExit("Stack missing RDSEndpoint, PrivateSubnetIds, or ECSSecurityGroupId.")
    if not db_password:
        raise SystemExit("DB password required for init_db (set POSTGRES_PASSWORD or pass --db-password).")

    lambda_dir = REPO_ROOT / "infra" / "lambda" / "init_db"
    if not (lambda_dir / "lambda_function.py").exists():
        raise SystemExit(f"Lambda code not found: {lambda_dir / 'lambda_function.py'}")

    with tempfile.TemporaryDirectory() as tmp:
        build_dir = Path(tmp) / "build"
        build_dir.mkdir()
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pg8000", "-t", str(build_dir), "--quiet", "--disable-pip-version-check"],
            check=True,
            capture_output=True,
        )
        # Copy handler into build dir so it is at package root in the zip
        shutil.copy(lambda_dir / "lambda_function.py", build_dir / "lambda_function.py")
        zip_path = Path(tmp) / "init_db.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in build_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(build_dir))

        lambda_name = f"{env_name}-init-db"
        lamb = session.client("lambda")
        payload = {
            "db_host": rds_host,
            "db_port": int(rds_port),
            "db_user": "postgres",
            "db_password": db_password,
            "db_name": "hte",
        }

        try:
            lamb.get_function(FunctionName=lambda_name)
            lamb.update_function_code(FunctionName=lambda_name, ZipFile=zip_path.read_bytes())
            print(f"Updated Lambda {lambda_name}, invoking...")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
            lamb.create_function(
                FunctionName=lambda_name,
                Runtime="python3.11",
                Role=role_arn,
                Handler="lambda_function.handler",
                Code={"ZipFile": zip_path.read_bytes()},
                Description="Create HTE database on RDS if not exists",
                Timeout=30,
                VpcConfig={
                    "SubnetIds": subnet_ids,
                    "SecurityGroupIds": [sg_id],
                },
            )
            print(f"Created Lambda {lambda_name}, invoking...")

        inv = lamb.invoke(FunctionName=lambda_name, InvocationType="RequestResponse", Payload=json.dumps(payload))
        result = json.loads(inv["Payload"].read())
        if result.get("status") == "ok":
            print("Init DB:", result.get("message", "ok"))
        else:
            print("Init DB error:", result.get("message", result), file=sys.stderr)
            raise SystemExit(1)


def write_extension_config(repo_root: Path, portal_url: str, gateway_url: str) -> None:
    """Write extension/config.aws.js with AWS URLs."""
    path = repo_root / "extension" / "config.aws.js"
    path.write_text(
        f"""/**
 * Extension config for AWS deployment (generated by scripts/aws_deploy.py).
 * Use this file when packaging the extension for production (or copy PORTAL_API_BASE / GATEWAY_BASE_URL into config.js).
 */
const CONFIG = {{
  PORTAL_API_BASE: '{portal_url.rstrip("/")}',
  GATEWAY_BASE_URL: '{gateway_url.rstrip("/")}',
}};

if (typeof globalThis !== 'undefined') {{
  globalThis.KIDS_SAFETY_CONFIG = CONFIG;
}}
"""
    )
    print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy HTE to AWS")
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), help="AWS region")
    parser.add_argument("--stack-name", default="hte-stack", help="CloudFormation stack name")
    parser.add_argument("--credentials-file", type=Path, default=REPO_ROOT / ".aws-deploy-credentials", help="Path to credentials file")
    parser.add_argument("--env-name", default=ENVIRONMENT_NAME, help="Environment name (prefix for resources)")
    parser.add_argument("--no-provision", action="store_true", help="[deploy] Skip CloudFormation; use existing stack")
    parser.add_argument("--skip-build", action="store_true", help="[deploy] Skip Docker build/push (use existing images)")
    subparsers = parser.add_subparsers(dest="command", help="Command (default: deploy)")
    subparsers.add_parser("deploy", help="Full deploy")
    migrate_parser = subparsers.add_parser("migrate", help="Run Django migrations via one-off ECS task")
    migrate_parser.add_argument("--stack-name", default="hte-stack", help="CloudFormation stack name")
    migrate_parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), help="AWS region")
    migrate_parser.add_argument("--env-name", default=ENVIRONMENT_NAME, help="Environment name (prefix for resources)")
    migrate_parser.add_argument("--credentials-file", type=Path, default=REPO_ROOT / ".aws-deploy-credentials", help="Path to credentials file")
    init_db_parser = subparsers.add_parser("init-db", help="Create application database on RDS via Lambda")
    init_db_parser.add_argument("--stack-name", default="hte-stack", help="CloudFormation stack name")
    init_db_parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), help="AWS region")
    init_db_parser.add_argument("--env-name", default=ENVIRONMENT_NAME, help="Environment name (prefix for resources)")
    init_db_parser.add_argument("--credentials-file", type=Path, default=REPO_ROOT / ".aws-deploy-credentials", help="Path to credentials file")
    args = parser.parse_args()
    if args.command is None:
        args.command = "deploy"

    creds = get_credentials(args.credentials_file)
    validate_credentials(args.region, creds)
    session = boto3.Session(
        aws_access_key_id=creds.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=creds.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=creds.get("AWS_SESSION_TOKEN"),
        region_name=args.region,
    )

    if args.command == "migrate":
        run_migrate(session, args.stack_name, args.env_name, args.region)
        return

    if args.command == "init-db":
        _load_dotenv_into_environ(REPO_ROOT / ".env")
        _load_dotenv_into_environ(REPO_ROOT / "backend" / ".env")
        db_password = os.environ.get("POSTGRES_PASSWORD") or ""
        if not db_password:
            try:
                getpass = __import__("getpass")
                db_password = getpass.getpass("DB password (RDS master): ")
            except ImportError:
                db_password = input("DB password (RDS master): ")
        run_init_db(session, args.stack_name, args.env_name, args.region, db_password)
        return

    account_id = session.client("sts").get_caller_identity()["Account"]

    # Load env from repo
    per_service, global_env, endpoint_keys = load_all_env(REPO_ROOT)
    # Merge portal env from backend .env (portal uses global only)
    portal_env = dict(global_env)
    endpoint_mapping: Dict[str, str] = {}

    if not args.no_provision:
        db_password = os.environ.get("POSTGRES_PASSWORD") or global_env.get("POSTGRES_PASSWORD") or ""
        if not db_password:
            try:
                getpass = __import__("getpass")
                db_password = getpass.getpass("DB password (for RDS): ")
            except ImportError:
                db_password = input("DB password (for RDS): ")
        if not db_password:
            raise SystemExit("POSTGRES_PASSWORD or DB password is required for provisioning.")
        template_path = REPO_ROOT / "infra" / "cloudformation" / "hte-infra.yaml"
        if not template_path.exists():
            raise SystemExit(f"Template not found: {template_path}")
        cfn = session.client("cloudformation")
        outputs = deploy_cloudformation(cfn, args.stack_name, args.region, template_path, db_password, args.env_name)
        endpoint_mapping = build_endpoint_mapping(outputs)
        # Ensure log groups exist for ECS
        logs = session.client("logs")
        for svc in SERVICES:
            ensure_log_group(logs, f"/ecs/{args.env_name}/{svc.replace('_', '-')}")
    else:
        cfn = session.client("cloudformation")
        outputs = get_stack_outputs(cfn, args.stack_name)
        if not outputs:
            raise SystemExit(f"Stack {args.stack_name} not found. Run without --no-provision first.")
        endpoint_mapping = build_endpoint_mapping(outputs)
        logs = session.client("logs")
        for svc in SERVICES:
            ensure_log_group(logs, f"/ecs/{args.env_name}/{svc.replace('_', '-')}")

    # Secrets Manager: one secret per service (JSON)
    secrets = session.client("secretsmanager")
    secret_arns: Dict[str, str] = {}
    for service_name, (port, ecr_suffix, context) in SERVICES.items():
        if service_name == "portal":
            env = dict(portal_env)
        elif service_name == "frontend":
            env = {}  # Frontend uses same-origin proxy; DJANGO_API_URL set in task env_overrides
        else:
            env = get_env_for_service(service_name, per_service, global_env)
        # Override with AWS endpoints
        if service_name == "portal":
            if "POSTGRES_HOST" in endpoint_mapping:
                env["POSTGRES_HOST"] = endpoint_mapping["POSTGRES_HOST"]
        elif service_name == "agent_gateway":
            for k, v in endpoint_mapping.items():
                if k.startswith("AGENT_GATEWAY_"):
                    env[k] = v
        secret_name = f"{args.env_name}/{service_name}"
        arn = put_secret(secrets, secret_name, env)
        secret_arns[service_name] = arn

    # ECR login
    ecr_login(args.region, account_id)

    # Build and push (optional); frontend uses same-origin /api/portal/* proxy (no NEXT_PUBLIC_API_URL so session cookies work)
    frontend_url_build = outputs.get("FrontendALBUrl", "http://localhost:3000")
    image_uris: Dict[str, str] = {}
    for service_name, (port, ecr_suffix, context) in SERVICES.items():
        build_args = None
        if service_name == "frontend":
            build_args = {
                "NEXT_PUBLIC_APP_URL": frontend_url_build,
                "NEXT_PUBLIC_API_URL": "",  # empty = same-origin /api/portal/* proxy so session cookies work
            }
        uri = build_and_push(
            REPO_ROOT,
            args.region,
            account_id,
            args.env_name,
            service_name,
            ecr_suffix,
            context,
            args.skip_build,
            build_args=build_args,
        )
        image_uris[service_name] = uri

    # Service discovery for internal services
    namespace_id = outputs.get("ServiceDiscoveryNamespaceId", "")
    discovery_services: Dict[str, str] = {}
    if namespace_id:
        sd = session.client("servicediscovery")
        internal = [s for s in SERVICES if s not in ("portal", "agent_gateway", "frontend")]
        ports = {s: SERVICES[s][0] for s in SERVICES}
        discovery_services = create_service_discovery_services(sd, namespace_id, internal, ports)

    # Get namespace ARN for service registry (needed for ECS serviceRegistries)
    # Service discovery: we need the service ARN for each. List namespaces and get registry ID.
    discovery_registry_arns: Dict[str, str] = {}
    if namespace_id:
        sd = session.client("servicediscovery")
        for name, sid in discovery_services.items():
            try:
                desc = sd.get_service(Id=sid)
                discovery_registry_arns[name] = desc["Service"]["Arn"]
            except Exception:
                pass

    execution_role_arn = outputs.get("ECSTaskExecutionRoleArn", "")
    task_role_arn = outputs.get("ECSTaskRoleArn", "")
    cluster_name = outputs.get("ECSClusterName", "")
    subnet_ids = (outputs.get("PrivateSubnetIds") or "").split(",")
    security_group_id = outputs.get("ECSSecurityGroupId", "")
    if not all([execution_role_arn, task_role_arn, cluster_name, subnet_ids, security_group_id]):
        raise SystemExit("Missing stack outputs (ECSTaskExecutionRoleArn, ECSClusterName, PrivateSubnetIds, ECSSecurityGroupId).")

    cpu = 256
    memory = 512
    task_defs: Dict[str, str] = {}
    frontend_url_for_cors = outputs.get("FrontendALBUrl", "")
    for service_name, (port, ecr_suffix, context) in SERVICES.items():
        if service_name == "portal":
            env_overrides = {"POSTGRES_HOST": endpoint_mapping.get("POSTGRES_HOST", "")}
            if frontend_url_for_cors:
                env_overrides["CORS_EXTRA_ORIGINS"] = frontend_url_for_cors
                # Django CSRF origin check: trust both http and https for the frontend ALB
                origins = [frontend_url_for_cors]
                if frontend_url_for_cors.startswith("http://"):
                    origins.append("https://" + frontend_url_for_cors[7:])
                elif frontend_url_for_cors.startswith("https://"):
                    origins.append("http://" + frontend_url_for_cors[8:])
                env_overrides["CSRF_TRUSTED_ORIGINS"] = ",".join(origins)
        elif service_name == "agent_gateway":
            env_overrides = {k: v for k, v in endpoint_mapping.items() if k.startswith("AGENT_GATEWAY_")}
        elif service_name == "frontend":
            # Next.js proxy (app/api/portal/[...path]) needs Django URL at runtime; browser stays same-origin
            portal_url = outputs.get("PortalALBUrl", "http://localhost:8000")
            env_overrides = {"DJANGO_API_URL": portal_url}
        else:
            env_overrides = {}
        task_def = register_task_definition(
            session.client("ecs"),
            args.env_name,
            service_name,
            image_uris[service_name],
            port,
            secret_arns[service_name],
            env_overrides,
            execution_role_arn,
            task_role_arn,
            cpu,
            memory,
            account_id,
            args.region,
        )
        task_defs[service_name] = task_def

    ecs = session.client("ecs")
    portal_tg = outputs.get("PortalTargetGroupArn", "")
    gateway_tg = outputs.get("GatewayTargetGroupArn", "")
    frontend_tg = outputs.get("FrontendTargetGroupArn", "")
    for service_name, (port, ecr_suffix, context) in SERVICES.items():
        container_name = service_name.replace("_", "-")
        tg_arn = None
        if service_name == "portal":
            tg_arn = portal_tg
        elif service_name == "agent_gateway":
            tg_arn = gateway_tg
        elif service_name == "frontend":
            tg_arn = frontend_tg
        discovery_arn = discovery_registry_arns.get(service_name) if service_name not in ("portal", "agent_gateway", "frontend") else None
        create_ecs_service(
            ecs,
            cluster_name,
            f"{args.env_name}-{container_name}",
            task_defs[service_name],
            subnet_ids,
            [security_group_id],
            tg_arn,
            container_name,
            port,
            discovery_registry_arn=discovery_arn,
        )

    portal_url = outputs.get("PortalALBUrl", "http://localhost:8000")
    gateway_url = outputs.get("GatewayALBUrl", "http://localhost:8003")
    frontend_url = outputs.get("FrontendALBUrl", "http://localhost:3000")
    print("\n--- Deployment complete ---")
    print(f"Frontend (portal UI): {frontend_url}")
    print(f"Portal API (extension PORTAL_API_BASE): {portal_url}")
    print(f"Gateway (extension GATEWAY_BASE_URL): {gateway_url}")
    write_extension_config(REPO_ROOT, portal_url, gateway_url)


if __name__ == "__main__":
    main()
