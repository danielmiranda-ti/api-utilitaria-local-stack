from functools import wraps
from typing import Any, Dict, Iterable, Tuple

from flask import jsonify, request


def get_json_body(
    required_fields: Iterable[str] = (),
) -> Tuple[Dict[str, Any] | None, Any]:
    """
    Lê o corpo JSON e valida campos obrigatórios.

    Retorna:
      (data, None) em caso de sucesso
      (None, (Response, status_code)) em caso de erro
    """
    data = request.get_json(silent=True)
    if data is None:
        return None, (jsonify({"error": "Invalid or missing JSON body"}), 400)

    for field in required_fields:
        value = data.get(field)
        if value is None or value == "":
            return None, (
                jsonify({"error": f"Missing required field in body: {field}"}),
                400,
            )

    return data, None


def require_query_params(*names: str):
    """
    Decorator que exige query params e injeta no kwargs da view.

    Exemplo:
      @require_query_params("table_name")
      def handler(table_name): ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            missing = [n for n in names if not request.args.get(n)]
            if missing:
                return (
                    jsonify(
                        {
                            "error": (
                                "Missing required query parameters: "
                                + ", ".join(missing)
                            )
                        }
                    ),
                    400,
                )

            for n in names:
                kwargs[n] = request.args.get(n)

            return func(*args, **kwargs)

        return wrapper

    return decorator
