"""Blueprint Flask para exposição de endpoints de leitura em tabelas DynamoDB."""

from functools import wraps
from typing import Any, Dict

from botocore.exceptions import ClientError
from flask import Blueprint, jsonify, request

from app.utils.aws import make_dynamodb_resource, client_error_response
from app.utils.http import require_query_params, get_json_body

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


# ----------------------------------------------------------------------
# Endpoint: criar tabela DynamoDB
# ----------------------------------------------------------------------
@dynamodb_bp.route("/v1/dynamodb/tables", methods=["POST"])
@with_dynamodb_client
def create_table(dynamodb):
    """
    Cria uma tabela DynamoDB.

    Corpo da requisição (JSON)
    --------------------------
    table_name : str (obrigatório)
        Nome da tabela a ser criada.
    partition_key_name : str (obrigatório)
        Nome do atributo de chave de partição (HASH).
    partition_key_type : str (obrigatório)
        Tipo do atributo de chave de partição. Valores permitidos:
        - "S" (String)
        - "N" (Number)
        - "B" (Binary)
    sort_key_name : str (opcional)
        Nome do atributo de chave de ordenação (RANGE).
    sort_key_type : str (opcional)
        Tipo do atributo de chave de ordenação ("S" | "N" | "B").
        Obrigatório se `sort_key_name` for informado.
    billing_mode : str (opcional, padrão: "PAY_PER_REQUEST")
        Modo de cobrança:
        - "PAY_PER_REQUEST" (on-demand)
        - "PROVISIONED"
    read_capacity_units : int (opcional, padrão: 5)
        Capacidade de leitura, usado apenas se `billing_mode = "PROVISIONED"`.
    write_capacity_units : int (opcional, padrão: 5)
        Capacidade de escrita, usado apenas se `billing_mode = "PROVISIONED"`.

    Returns
    -------
    201 Created
        JSON com informações básicas da tabela criada.
    400 Bad Request
        - Corpo ausente ou inválido.
        - Campos obrigatórios ausentes.
        - Combinação inválida de parâmetros.
    500 Internal Server Error
        Em caso de erro ao acessar o DynamoDB.
    """
    try:
        # Campos sempre obrigatórios
        data, error = get_json_body(
            required_fields=["table_name", "partition_key_name", "partition_key_type"]
        )
        if error:
            return error

        table_name: str = data["table_name"]
        partition_key_name: str = data["partition_key_name"]
        partition_key_type: str = data["partition_key_type"]

        # Validação simples do tipo da chave
        if partition_key_type not in ("S", "N", "B"):
            return (
                jsonify(
                    {
                        "error": "Invalid partition_key_type. "
                        "Allowed values: 'S', 'N', 'B'."
                    }
                ),
                400,
            )

        sort_key_name: str | None = data.get("sort_key_name")
        sort_key_type: str | None = data.get("sort_key_type")

        if sort_key_name and not sort_key_type:
            return (
                jsonify(
                    {
                        "error": "sort_key_type is required when sort_key_name is provided."
                    }
                ),
                400,
            )

        if sort_key_type and sort_key_type not in ("S", "N", "B"):
            return (
                jsonify(
                    {
                        "error": "Invalid sort_key_type. "
                        "Allowed values: 'S', 'N', 'B'."
                    }
                ),
                400,
            )

        billing_mode: str = data.get("billing_mode", "PAY_PER_REQUEST")
        if billing_mode not in ("PAY_PER_REQUEST", "PROVISIONED"):
            return (
                jsonify(
                    {
                        "error": "Invalid billing_mode. "
                        "Allowed values: 'PAY_PER_REQUEST', 'PROVISIONED'."
                    }
                ),
                400,
            )

        # Monta definições de atributos e chave
        attribute_definitions = [
            {
                "AttributeName": partition_key_name,
                "AttributeType": partition_key_type,
            }
        ]
        key_schema = [
            {
                "AttributeName": partition_key_name,
                "KeyType": "HASH",
            }
        ]

        if sort_key_name is not None and sort_key_type is not None:
            attribute_definitions.append(
                {
                    "AttributeName": sort_key_name,
                    "AttributeType": sort_key_type,
                }
            )
            key_schema.append(
                {
                    "AttributeName": sort_key_name,
                    "KeyType": "RANGE",
                }
            )

        create_kwargs: Dict[str, Any] = {
            "TableName": table_name,
            "AttributeDefinitions": attribute_definitions,
            "KeySchema": key_schema,
            "BillingMode": billing_mode,
        }

        # Se modo provisionado, adiciona capacidade
        if billing_mode == "PROVISIONED":
            read_capacity = int(data.get("read_capacity_units", 5))
            write_capacity = int(data.get("write_capacity_units", 5))
            create_kwargs["ProvisionedThroughput"] = {
                "ReadCapacityUnits": read_capacity,
                "WriteCapacityUnits": write_capacity,
            }

        # Cria a tabela
        table = dynamodb.create_table(**create_kwargs)

        # Opcional: em LocalStack costuma ser imediato; na AWS real, pode ficar "CREATING"
        return (
            jsonify(
                {
                    "table_name": table_name,
                    "table_status": getattr(table, "table_status", None),
                    "table_arn": getattr(table, "table_arn", None),
                    "billing_mode": billing_mode,
                }
            ),
            201,
        )

    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Endpoint: criar/atualizar item em uma tabela DynamoDB (put_item)
# ----------------------------------------------------------------------
@dynamodb_bp.route("/v1/dynamodb/item", methods=["POST"])
@with_dynamodb_client
@require_query_params("table_name")
def put_item(dynamodb, table_name: str):
    """
    Cria ou atualiza um item em uma tabela DynamoDB (operação put_item).

    Query parameters
    ----------------
    table_name : str (obrigatório)
        Nome da tabela DynamoDB.

    Corpo da requisição (JSON)
    --------------------------
    item : object (obrigatório)
        Objeto JSON representando o item completo a ser salvo na tabela.
        As chaves definidas no schema da tabela (partition key e sort key,
        se houver) devem estar presentes neste objeto.

    Returns
    -------
    201 Created
        JSON com o item salvo e o nome da tabela.
    400 Bad Request
        - Corpo ausente ou inválido.
        - Campo `item` ausente ou com tipo inválido.
    500 Internal Server Error
        Em caso de erro ao acessar o DynamoDB.
    """
    try:
        # Corpo obrigatório com o campo "item"
        data, error = get_json_body(required_fields=["item"])
        if error:
            return error

        item = data["item"]
        if not isinstance(item, dict):
            return jsonify({"error": "`item` must be an object (JSON)."}), 400

        table = dynamodb.Table(table_name)
        table.put_item(Item=item)

        return jsonify({"table_name": table_name, "item": item}), 201

    except ClientError as e:
        return client_error_response(e)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
