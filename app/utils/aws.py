from typing import Optional

import boto3
from botocore.exceptions import ClientError
from flask import current_app, jsonify


def get_aws_endpoint(config_key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Lê o endpoint de um serviço AWS da config do Flask, com fallback.
    """
    return current_app.config.get(config_key, default)


def get_aws_region(default: str = "us-east-1") -> str:
    """Lê a região AWS da config do Flask, com fallback para um default."""
    return current_app.config.get("AWS_REGION", default)


def make_sns_client() -> "botocore.client.SNS":
    """
    Cria cliente SNS usando:
      - app.config["SNS_ENDPOINT_URL"], se existir
      - senão, "http://localhost:4566" (LocalStack)
    """
    endpoint = get_aws_endpoint("SNS_ENDPOINT_URL", "http://localhost:4566")
    region = get_aws_region()
    return boto3.client("sns", region_name=region, endpoint_url=endpoint)

def make_dynamodb_resource() -> "boto3.resources.base.ServiceResource":
    """Cria recurso DynamoDB com endpoint configurável (LocalStack por padrão)."""
    endpoint = get_aws_endpoint("DYNAMODB_ENDPOINT_URL", "http://localhost:4566")
    region = get_aws_region()
    return boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint)

def make_sqs_client() -> "botocore.client.SQS":
    """Cria cliente SQS com endpoint configurável (LocalStack por padrão)."""
    endpoint = get_aws_endpoint("SQS_ENDPOINT_URL", "http://localhost:4566")
    region = get_aws_region()
    return boto3.client("sqs", region_name=region, endpoint_url=endpoint)

# ---------- helpers reutilizáveis p/ SQS ----------

def get_queue_url_by_name(sqs, queue_name: str) -> str:
    """Resolve o `queue_url` a partir do `queue_name` usando `get_queue_url`."""
    resp = sqs.get_queue_url(QueueName=queue_name)
    return resp["QueueUrl"]


def resolve_queue_arn_by_name(sqs, queue_name: str) -> Optional[str]:
    """Resolve o ARN de uma fila SQS a partir do nome."""
    queue_url = get_queue_url_by_name(sqs, queue_name)
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["QueueArn"],
    )
    return attrs["Attributes"]["QueueArn"]

def client_error_response(e: ClientError):
    """
    Converte um ClientError em resposta HTTP 500 padronizada.
    """
    return (
        jsonify(
            {
                "error": e.response.get("Error", {}).get(
                    "Message",
                    str(e),
                )
            }
        ),
        500,
    )
