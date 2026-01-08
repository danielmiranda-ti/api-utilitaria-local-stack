"""Blueprint Flask para exposição de endpoints de interação com filas SQS."""

from functools import wraps
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError
from flask import Blueprint, jsonify, request

from app.utils.aws import make_sqs_client, client_error_response, get_queue_url_by_name
from app.utils.http import require_query_params

sqs_bp = Blueprint("sqs", __name__)


# ----------------------------------------------------------------------
# Decorator para injetar cliente SQS
# ----------------------------------------------------------------------
def with_sqs_client(func):
    """
    Decorator que injeta um cliente SQS do boto3 na view Flask.

    A função decorada deve aceitar um parâmetro nomeado `sqs`.

    Exemplo
    -------
    @with_sqs_client
    def handler(sqs):
        sqs.list_queues()
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        kwargs["sqs"] = make_sqs_client()
        return func(*args, **kwargs)

    return wrapper


# ----------------------------------------------------------------------
# Endpoint: enviar mensagem para a fila (por nome)
# ----------------------------------------------------------------------
@sqs_bp.route("/v1/sqs/send", methods=["POST"])
@with_sqs_client
@require_query_params("queue_name")
def send_message(sqs, queue_name: str):
    """
    Envia uma mensagem para uma fila SQS, recebendo apenas o nome da fila.

    Query parameters
    ----------------
    queue_name : str (obrigatório)
        Nome da fila SQS. A API resolve o `queue_url` internamente.

    Corpo da requisição (JSON)
    --------------------------
    message : str (obrigatório)
        Conteúdo da mensagem a ser enviada.
    delay_seconds : int (opcional)
        Atraso em segundos para disponibilizar a mensagem.
    attributes : dict[str, dict[str, str]] (opcional)
        Atributos da mensagem no formato aceito pelo SQS, ex.:
        {
            "attribute_name": {
                "DataType": "String" | "Number" | "Binary",
                "StringValue": "value",
                "BinaryValue": "base64-encoded"
            },
            ...
        }

    Returns
    -------
    200 OK
        JSON com o `MessageId` e `queue_name`.
    400 Bad Request
        Se o corpo for inválido ou faltar `message`.
    500 Internal Server Error
        Em caso de erro ao acessar o SQS.
    """
    try:
        data: Optional[Dict[str, Any]] = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid or missing JSON body"}), 400

        message: Optional[str] = data.get("message")
        if not message:
            return (
                jsonify({"error": "Missing required field in body: message"}),
                400,
            )

        delay_seconds: Optional[int] = data.get("delay_seconds")
        attributes: Optional[Dict[str, Any]] = data.get("attributes")

        queue_url = get_queue_url_by_name(sqs, queue_name)

        send_kwargs: Dict[str, Any] = {
            "QueueUrl": queue_url,
            "MessageBody": message,
        }
        if delay_seconds is not None:
            send_kwargs["DelaySeconds"] = int(delay_seconds)
        if attributes:
            send_kwargs["MessageAttributes"] = attributes

        response = sqs.send_message(**send_kwargs)

        return (
            jsonify(
                {
                    "message_id": response.get("MessageId"),
                    "queue_name": queue_name,
                }
            ),
            200,
        )
    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Endpoint: receber mensagens da fila (por nome)
# ----------------------------------------------------------------------
@sqs_bp.route("/v1/sqs/messages", methods=["GET"])
@with_sqs_client
@require_query_params("queue_name")
def receive_messages(sqs, queue_name: str):
    """
    Recebe mensagens de uma fila SQS, informando apenas o nome da fila.

    Query parameters
    ----------------
    queue_name : str (obrigatório)
        Nome da fila SQS.
    max_number : int (opcional, padrão: 1, máx: 10)
        Quantidade máxima de mensagens a retornar.
    wait_time_seconds : int (opcional, padrão: 0, máx: 20)
        Long polling em segundos.

    Returns
    -------
    200 OK
        JSON com lista de `messages`. Cada item contém `Body`,
        `ReceiptHandle`, `MessageId` etc.
    500 Internal Server Error
        Em caso de erro ao acessar o SQS.
    """
    try:
        max_number = request.args.get("max_number", default="1")
        wait_time_seconds = request.args.get("wait_time_seconds", default="0")

        max_number_int = max(min(int(max_number), 10), 1)
        wait_time_int = max(min(int(wait_time_seconds), 20), 0)

        queue_url = get_queue_url_by_name(sqs, queue_name)

        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_number_int,
            WaitTimeSeconds=wait_time_int,
            MessageAttributeNames=["All"],
        )

        messages: List[Dict[str, Any]] = response.get("Messages", [])

        return jsonify({"queue_name": queue_name, "messages": messages}), 200
    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Endpoint: listar filas
# ----------------------------------------------------------------------
@sqs_bp.route("/v1/sqs/queues", methods=["GET"])
@with_sqs_client
def list_queues(sqs):
    """
    Lista filas SQS disponíveis.

    Query parameters
    ----------------
    prefix : str (opcional)
        Prefixo para filtrar nomes de filas (QueueNamePrefix).

    Returns
    -------
    200 OK
        JSON com a lista de `queue_urls`.
    500 Internal Server Error
        Em caso de erro ao acessar o SQS.
    """
    try:
        prefix = request.args.get("prefix")

        list_kwargs: Dict[str, Any] = {}
        if prefix:
            list_kwargs["QueueNamePrefix"] = prefix

        response = sqs.list_queues(**list_kwargs)
        queue_urls = response.get("QueueUrls", [])

        return jsonify({"queue_urls": queue_urls}), 200
    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------------------------------
# Endpoint: deletar UMA mensagem específica da fila
# ----------------------------------------------------------------------
@sqs_bp.route("/v1/sqs/messages", methods=["DELETE"])
@with_sqs_client
@require_query_params("queue_name")
def delete_message(sqs, queue_name: str):
    """
    Deleta uma mensagem específica de uma fila SQS.

    Query parameters
    ----------------
    queue_name : str (obrigatório)
        Nome da fila SQS.
    receipt_handle : str (obrigatório)
        ReceiptHandle da mensagem a ser deletada.

    Returns
    -------
    200 OK
        JSON com resultado da deleção.
    400 Bad Request
        Se faltar o receipt_handle.
    500 Internal Server Error
        Em caso de erro ao acessar o SQS.
    """
    try:
        receipt_handle = request.args.get("receipt_handle")
        if not receipt_handle:
            return (
                jsonify({"error": "Missing required query parameter: receipt_handle"}),
                400,
            )

        queue_url = get_queue_url_by_name(sqs, queue_name)

        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )

        return (
            jsonify(
                {
                    "queue_name": queue_name,
                    "receipt_handle": receipt_handle,
                    "deleted": True,
                }
            ),
            200,
        )
    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Endpoint: deletar TODAS as mensagens da fila (purge)
# ----------------------------------------------------------------------
@sqs_bp.route("/v1/sqs/messages/all", methods=["DELETE"])
@with_sqs_client
@require_query_params("queue_name")
def purge_queue(sqs, queue_name: str):
    """
    Remove todas as mensagens (visíveis e invisíveis) de uma fila SQS.

    Query parameters
    ----------------
    queue_name : str (obrigatório)
        Nome da fila SQS.

    Observação
    ----------
    - Usa PurgeQueue, que só pode ser chamado no máximo 1 vez a cada 60 segundos.
    - A remoção é assíncrona: as mensagens podem levar algum tempo para sumir.

    Returns
    -------
    200 OK
        JSON indicando que o purge foi solicitado.
    500 Internal Server Error
        Em caso de erro ao acessar o SQS.
    """
    try:
        queue_url = get_queue_url_by_name(sqs, queue_name)

        sqs.purge_queue(QueueUrl=queue_url)

        return (
            jsonify(
                {
                    "queue_name": queue_name,
                    "purged": True,
                    "note": "Purge solicitado; operação é assincrona no SQS.",
                }
            ),
            200,
        )
    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
