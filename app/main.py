import os
from flask import Flask

# Importa os blueprints
from app.routes.dynamodb import dynamodb_bp
from app.routes.sns import sns_bp
from app.routes.sqs import sqs_bp

app = Flask(__name__)

app.config["AWS_REGION"] = os.getenv("AWS_REGION", "us-east-1")

# (opcional) configs dos endpoints AWS / LocalStack
app.config["DYNAMODB_ENDPOINT_URL"] = os.getenv("DYNAMODB_ENDPOINT_URL", "http://localhost:4566")
app.config["SNS_ENDPOINT_URL"] = os.getenv("SNS_ENDPOINT_URL", "http://localhost:4566")
app.config["SQS_ENDPOINT_URL"] = os.getenv("SQS_ENDPOINT_URL", "http://localhost:4566")

# Registro dos blueprints
app.register_blueprint(dynamodb_bp)
app.register_blueprint(sns_bp)
app.register_blueprint(sqs_bp)

if __name__ == "__main__":
    app.run(debug=True, port=8000)