"""Blueprint Flask para criação de tópicos SNS e publicação de mensagens.

Este módulo expõe endpoints HTTP para:

- Criar tópicos SNS (`POST /v1/sns/topics`)
- Publicar mensagens em tópicos SNS a partir do nome (`POST /v1/sns/publish`)
- Listar tópicos SNS (`GET /v1/sns/topics`)

Todos os endpoints utilizam LocalStack ou AWS real, de acordo com a
configuração de `make_sns_client`.
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional

from botocore.exceptions import ClientError
from flask import Blueprint, jsonify, request

from app.utils.aws import make_sns_client, client_error_response, make_sqs_client, resolve_queue_arn_by_name
from app.utils.http import get_json_body, require_query_params

sns_bp = Blueprint("sns", __name__)


# ----------------------------------------------------------------------
# Decorators
# ----------------------------------------------------------------------
def with_sns_client(func: Callable):
    """
    Decorator que injeta um cliente SNS do boto3 na view Flask.

    A função decorada deve aceitar um parâmetro nomeado `sns`, que será
    uma instância de `botocore.client.SNS` criada por `make_sns_client()`.

    Exemplo
    -------
    @with_sns_client
    def handler(sns):
        sns.list_topics()
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        kwargs["sns"] = make_sns_client()
        return func(*args, **kwargs)

    return wrapper


# ----------------------------------------------------------------------
# Helpers específicos de SNS
# ----------------------------------------------------------------------
def resolve_topic_arn_by_name(sns, topic_name: str) -> Optional[str]:
    """
    Resolve o ARN de um tópico SNS a partir do nome lógico.

    Estratégia:
    -----------
    - Usa o paginator de `list_topics` para percorrer todos os tópicos.
    - Para cada `TopicArn`, extrai o último segmento após ':'.
      Exemplo: arn:aws:sns:us-east-1:123456789012:meu-topico -> "meu-topico"
    - Compara esse nome com `topic_name`.

    Parâmetros
    ----------
    sns : botocore.client.SNS
        Cliente SNS já inicializado.
    topic_name : str
        Nome lógico do tópico SNS (parte final do ARN).

    Retorna
    -------
    str | None
        - ARN completo do tópico, se encontrado.
        - None, caso nenhum tópico com esse nome exista.
    """
    paginator = sns.get_paginator("list_topics")

    for page in paginator.paginate():
        for topic in page.get("Topics", []):
            arn = topic.get("TopicArn")
            if not arn:
                continue
            # Nome do tópico = último pedaço do ARN
            # ex.: arn:aws:sns:us-east-1:123456789012:meu-topico
            name_from_arn = arn.split(":")[-1]
            if name_from_arn == topic_name:
                return arn

    return None


# ----------------------------------------------------------------------
# Serviço para CRIAR tópico
# ----------------------------------------------------------------------
@sns_bp.route("/v1/sns/topics", methods=["POST"])
@with_sns_client
def create_topic(sns):
    """
    Cria um tópico SNS a partir do nome.

    Corpo da requisição (JSON)
    --------------------------
    name : str (obrigatório)
        Nome lógico do tópico SNS a ser criado.

    Comportamento
    -------------
    - Usa `sns.create_topic(Name=name)`, que é idempotente.
    - Se o tópico já existir, o SNS apenas retorna o ARN existente.

    Retornos
    --------
    201 Created
        JSON no formato:
        {
          "name": "<nome_do_topico>",
          "topic_arn": "<arn:aws:sns:...>"
        }
    400 Bad Request
        - Corpo ausente ou inválido.
        - Campo obrigatório `name` ausente.
    500 Internal Server Error
        - Erro ao acessar o SNS (ClientError ou exceção inesperada).
    """
    try:
        data, error = get_json_body(required_fields=["name"])
        if error:
            return error

        name: str = data["name"]

        resp = sns.create_topic(Name=name)
        topic_arn = resp.get("TopicArn")

        return (
            jsonify(
                {
                    "name": name,
                    "topic_arn": topic_arn,
                }
            ),
            201,
        )

    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Serviço para PUBLICAR mensagem (obrigatório topic_name)
# ----------------------------------------------------------------------
@sns_bp.route("/v1/sns/publish", methods=["POST"])
@with_sns_client
@require_query_params("topic_name")
def publish_message(sns, topic_name: str):
    """
    Publica uma mensagem em um tópico SNS, resolvendo o ARN pelo nome.

    Query parameters
    ----------------
    topic_name : str (obrigatório)
        Nome lógico do tópico SNS. O tópico deve existir previamente;
        este endpoint não o cria.

    Corpo da requisição (JSON)
    --------------------------
    message : str (obrigatório)
        Conteúdo da mensagem a ser publicada.
    subject : str (opcional)
        Assunto da mensagem. Útil, por exemplo, para protocolos de e-mail.
    attributes : dict[str, dict[str, str]] (opcional)
        Atributos de mensagem no formato aceito pelo SNS, por exemplo:
        {
          "attribute_name": {
            "DataType": "String" | "Number" | "Binary",
            "StringValue": "value",
            "BinaryValue": "base64-encoded"
          }
        }

    Fluxo
    -----
    1. Resolve `topic_arn` via `resolve_topic_arn_by_name`.
    2. Se não encontrar, retorna HTTP 404 (não cria o tópico).
    3. Lê e valida o corpo JSON, exigindo o campo `message`.
    4. Chama `sns.publish` com `TopicArn`, `Message` e, se presentes,
       `Subject` e `MessageAttributes`.

    Retornos
    --------
    200 OK
        JSON no formato:
        {
          "message_id": "<id_da_mensagem>",
          "topic_arn": "<arn_do_topico>",
          "topic_name": "<nome_do_topico>"
        }
    400 Bad Request
        - Corpo ausente ou inválido.
        - Campo obrigatório `message` ausente.
    404 Not Found
        - Tópico com o nome informado não encontrado.
    500 Internal Server Error
        - Erro ao acessar o SNS (ClientError ou exceção inesperada).
    """
    try:
        # Procura o ARN a partir do nome (NÃO cria o tópico aqui)
        topic_arn = resolve_topic_arn_by_name(sns, topic_name)
        if not topic_arn:
            return (
                jsonify(
                    {
                        "error": "Topic not found",
                        "details": f"Topic with name '{topic_name}' was not found",
                    }
                ),
                404,
            )

        data, error = get_json_body(required_fields=["message"])
        if error:
            return error

        message: str = data["message"]
        subject: str | None = data.get("subject")
        attributes: Dict[str, Any] | None = data.get("attributes")

        publish_kwargs: Dict[str, Any] = {
            "TopicArn": topic_arn,
            "Message": message,
        }

        if subject:
            publish_kwargs["Subject"] = subject
        if attributes:
            publish_kwargs["MessageAttributes"] = attributes

        resp = sns.publish(**publish_kwargs)

        return (
            jsonify(
                {
                    "message_id": resp.get("MessageId"),
                    "topic_arn": topic_arn,
                    "topic_name": topic_name,
                }
            ),
            200,
        )

    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Serviço para LISTAR tópicos
# ----------------------------------------------------------------------
@sns_bp.route("/v1/sns/topics", methods=["GET"])
@with_sns_client
def list_topics(sns):
    """
    Lista todos os tópicos SNS disponíveis.

    Comportamento
    -------------
    - Usa o paginator de `list_topics` para percorrer todos os tópicos.
    - Para cada `TopicArn`, deriva o nome lógico a partir do último
      segmento do ARN.

    Retornos
    --------
    200 OK
        JSON no formato:
        {
          "topics": [
            {
              "topic_arn": "<arn:aws:sns:...>",
              "name": "<nome_do_topico>"
            },
            ...
          ]
        }
    500 Internal Server Error
        - Erro ao acessar o SNS (ClientError ou exceção inesperada).
    """
    try:
        topics = []
        paginator = sns.get_paginator("list_topics")

        for page in paginator.paginate():
            for topic in page.get("Topics", []):
                arn = topic.get("TopicArn")
                if not arn:
                    continue
                name = arn.split(":")[-1]
                topics.append(
                    {
                        "topic_arn": arn,
                        "name": name,
                    }
                )

        return jsonify({"topics": topics}), 200

    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sns_bp.route("/v1/sns/subscriptions", methods=["POST"])
@with_sns_client
def create_subscription(sns):
    """
    Cria uma subscription SNS para SQS ou Lambda.

    Body JSON:
    - topic_name (ou topic_arn)
    - type: "sqs" | "lambda"
    - queue_name (ou queue_arn)  [se type == "sqs"]
    - lambda_arn                  [se type == "lambda"]
    """
    try:
        data, error = get_json_body()
        if error:
            return error

        topic_arn = data.get("topic_arn")
        topic_name = data.get("topic_name")
        sub_type = data.get("type")

        if not sub_type or sub_type not in ("sqs", "lambda"):
            return jsonify({"error": "type must be 'sqs' or 'lambda'"}), 400

        # Resolve topic_arn se vier só o nome
        if not topic_arn and topic_name:
            topic_arn = resolve_topic_arn_by_name(sns, topic_name)

        if not topic_arn:
            return jsonify({"error": "topic_arn or topic_name is required"}), 400

        # Monta protocol/endpoint conforme tipo
        if sub_type == "sqs":
            queue_arn = data.get("queue_arn")
            queue_name = data.get("queue_name")

            if not queue_arn and queue_name:
                sqs = make_sqs_client()
                queue_arn = resolve_queue_arn_by_name(sqs, queue_name)

            if not queue_arn:
                return jsonify(
                    {"error": "queue_arn or queue_name is required for type 'sqs'"}
                ), 400

            protocol = "sqs"
            endpoint = queue_arn

        elif sub_type == "lambda":
            lambda_arn = data.get("lambda_arn")
            if not lambda_arn:
                return jsonify(
                    {"error": "lambda_arn is required for type 'lambda'"}
                ), 400

            protocol = "lambda"
            endpoint = lambda_arn

            # Em AWS real, normalmente é preciso garantir a permission:
            # lambda_client.add_permission(
            #     FunctionName=lambda_arn,
            #     StatementId="sns-invoke",
            #     Action="lambda:InvokeFunction",
            #     Principal="sns.amazonaws.com",
            #     SourceArn=topic_arn,
            # )

        resp = sns.subscribe(
            TopicArn=topic_arn,
            Protocol=protocol,
            Endpoint=endpoint,
            Attributes={
                # Mantém mensagens "cruas" para SQS (útil em LocalStack)
                "RawMessageDelivery": "true"
            }
            if protocol == "sqs"
            else {},
        )

        return jsonify(
            {
                "subscription_arn": resp.get("SubscriptionArn"),
                "topic_arn": topic_arn,
                "protocol": protocol,
                "endpoint": endpoint,
            }
        ), 201

    except ClientError as e:
        from app.utils.aws import client_error_response

        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500