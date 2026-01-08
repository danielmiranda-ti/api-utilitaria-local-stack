#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="localstack"
IMAGE_NAME="localstack/localstack:latest"
SERVICES="dynamodb,sns,sqs"

# Porta principal do LocalStack
PORT="4566"

echo "Parando e removendo container antigo (${CONTAINER_NAME}), se existir..."
if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
  docker rm -f "${CONTAINER_NAME}"
fi

echo "Subindo LocalStack (${IMAGE_NAME}) com serviços: ${SERVICES}"

docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:${PORT}" \
  -p 4510-4559:4510-4559 \
  -e SERVICES="${SERVICES}" \
  -e DEBUG=1 \
  -v "/var/run/docker.sock:/var/run/docker.sock" \
  "${IMAGE_NAME}"

echo "LocalStack iniciado em http://localhost:${PORT}"
echo "Serviços habilitados: ${SERVICES}"