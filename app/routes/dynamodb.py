"""Blueprint Flask para exposição de endpoints de leitura em tabelas DynamoDB."""

from functools import wraps
from typing import Any, Dict

from botocore.exceptions import ClientError
from flask import Blueprint, jsonify, request

from app.utils.aws import make_dynamodb_resource, client_error_response
from app.utils.http import require_query_params

dynamodb_bp = Blueprint("dynamodb", __name__)


# ----------------------------------------------------------------------
# Decorator para injetar recurso DynamoDB
# ----------------------------------------------------------------------
def with_dynamodb_client(func):
    """
    Decorator que injeta um recurso DynamoDB do boto3 na view Flask.

    A função decorada deve aceitar um parâmetro nomeado `dynamodb`.

    Exemplo
    -------
    @with_dynamodb_client
    def handler(dynamodb):
        table = dynamodb.Table("minha_tabela")
        ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        kwargs["dynamodb"] = make_dynamodb_resource()
        return func(*args, **kwargs)

    return wrapper


# ----------------------------------------------------------------------
# Endpoint: listar todos os itens (scan)
# ----------------------------------------------------------------------
@dynamodb_bp.route("/v1/dynamodb/all", methods=["GET"])
@with_dynamodb_client
@require_query_params("table_name")
def get_all_items(dynamodb, table_name: str):
    """
    Retorna todos os itens de uma tabela DynamoDB (operação scan).

    Query parameters
    ----------------
    table_name : str (obrigatório)
        Nome da tabela DynamoDB.

    Returns
    -------
    200 OK
        JSON com `items` (lista de itens) e `table_name`.
    500 Internal Server Error
        Em caso de erro ao acessar o DynamoDB.
    """
    try:
        table = dynamodb.Table(table_name)
        response = table.scan()
        items = response.get("Items", [])
        return jsonify({"items": items, "table_name": table_name}), 200

    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Endpoint: obter um item pela chave (partition + sort key opcional)
# ----------------------------------------------------------------------
@dynamodb_bp.route("/v1/dynamodb/item", methods=["GET"])
@with_dynamodb_client
@require_query_params("table_name", "partition_key_name", "partition_key_value")
def get_item(
    dynamodb,
    table_name: str,
    partition_key_name: str,
    partition_key_value: str,
):
    """
    Retorna um único item de uma tabela DynamoDB, dado chave de partição
    (e opcionalmente sort key).

    Query parameters
    ----------------
    table_name : str (obrigatório)
        Nome da tabela DynamoDB.
    partition_key_name : str (obrigatório)
        Nome do atributo de chave de partição.
    partition_key_value : str (obrigatório)
        Valor da chave de partição.
    sort_key_name : str (opcional)
        Nome do atributo de chave de ordenação.
    sort_key_value : str (opcional)
        Valor da chave de ordenação.

    Returns
    -------
    200 OK
        JSON com o item encontrado.
    400 Bad Request
        Se parâmetros obrigatórios estiverem ausentes (tratado pelo decorator).
    404 Not Found
        Se o item não for encontrado.
    500 Internal Server Error
        Em caso de erro ao acessar o DynamoDB.
    """
    try:
        table = dynamodb.Table(table_name)

        # Campos opcionais (sort key)
        sort_key_name = request.args.get("sort_key_name")
        sort_key_value = request.args.get("sort_key_value")

        # OBS: se suas chaves forem numéricas/booleanas, converta aqui.
        key: Dict[str, Any] = {partition_key_name: partition_key_value}
        if sort_key_name and sort_key_value:
            key[sort_key_name] = sort_key_value

        response = table.get_item(Key=key)
        item = response.get("Item")

        if not item:
            return jsonify({"error": "Item not found."}), 404

        return jsonify(item), 200

    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500