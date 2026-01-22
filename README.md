# 🔧 Serviço REST para SNS/SQS/DynamoDB (LocalStack)

Serviço em **Python/Flask** que expõe uma API REST para trabalhar com **SQS**, **SNS** e **DynamoDB** usando o **LocalStack** como mock da AWS.

---

## 📦 Pré-requisitos

1. 🐍 **Python** 3.10+ (ou versão que você estiver usando)  
2. 🐳 **Docker** instalado e executando  
3. 🧱 Imagem do **LocalStack** (`localstack/localstack:latest`)  
4. 📦 `pip` para instalar dependências  

---

## 🐳 Subindo o LocalStack

O projeto já possui um script para subir o LocalStack:

```bash
chmod +x run-local-stack.sh
./run-local-stack.sh
```

Isso irá:

- Parar/remover um container antigo `localstack` (se existir)
- Subir o container `localstack/localstack:latest`
- Habilitar os serviços: `dynamodb`, `sns`, `sqs`
- Expor o LocalStack em: `http://localhost:4566`

---

## ⚙️ Instalação do Projeto

Dentro da pasta do projeto:

```bash
    # 1. (Opcional, mas recomendado) criar e ativar um ambiente virtual
    python -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    # .venv\Scripts\activate   # Windows (PowerShell/CMD)
    
    # 2. Instalar dependências
    pip install -r app/requirements.txt
```

---

## 🔧 Configuração

As credenciais, região e endpoints são lidos via variáveis de ambiente e usados em `app/main.py` + `app/utils/aws.py`:

```bash
    # Região AWS
    export AWS_REGION=us-east-1
    
    # Endpoints do LocalStack
    export DYNAMODB_ENDPOINT_URL=http://localhost:4566
    export SNS_ENDPOINT_URL=http://localhost:4566
    export SQS_ENDPOINT_URL=http://localhost:4566
    
    # Credenciais fake para o boto3 (LocalStack ignora valores reais)
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
```

Se não definir essas variáveis, o código usa os seguintes **defaults**:

- `AWS_REGION`: `us-east-1`
- `*_ENDPOINT_URL`: `http://localhost:4566`

---

## 🚀 Executando o Serviço

O ponto de entrada do Flask é `app/main.py`:

```bash
    export FLASK_APP=app.main
    export FLASK_ENV=development
    
    flask run --host=0.0.0.0 --port=8000
```

A API ficará disponível em:

```text
http://localhost:8000
```

---

## 🌐 Endpoints

### 📚 DynamoDB

#### 1. Listar todos os itens de uma tabela

```http
GET /v1/dynamodb/all
```

**Query params**

- `table_name` (obrigatório): nome da tabela DynamoDB.

**Exemplo**

```bash
  curl "http://localhost:8000/v1/dynamodb/all?table_name=MinhaTabela"
```

**Resposta (exemplo)**

```json
{
  "table_name": "MinhaTabela",
  "items": [
    {
      "id": "1",
      "name": "Item 1"
    }
  ]
}
```

---

#### 2. Obter item por chave

```http
GET /v1/dynamodb/item
```

**Query params**

- `table_name` (obrigatório): nome da tabela.  
- `partition_key_name` (obrigatório): nome da chave de partição.  
- `partition_key_value` (obrigatório): valor da chave de partição.  
- `sort_key_name` (opcional): nome da sort key.  
- `sort_key_value` (opcional): valor da sort key.  

**Exemplo**

```bash
  curl "http://localhost:8000/v1/dynamodb/item?table_name=MinhaTabela&partition_key_name=id&partition_key_value=1"
```

**Resposta (exemplo)**

```json
{
  "id": "1",
  "name": "Item 1"
}
```

---

#### 3. Criar tabela DynamoDB

```http
POST /v1/dynamodb/tables
```

**Body (JSON)**

- `table_name` (obrigatório): nome da tabela a ser criada.  
- `partition_key_name` (obrigatório): nome do atributo de chave de partição (HASH).  
- `partition_key_type` (obrigatório): tipo do atributo de chave de partição:
  - `"S"` – String  
  - `"N"` – Number  
  - `"B"` – Binary  

- `sort_key_name` (opcional): nome do atributo de chave de ordenação (RANGE).  
- `sort_key_type` (opcional): tipo do atributo de chave de ordenação (`"S"`, `"N"`, `"B"`).  
  > Obrigatório se `sort_key_name` for informado.

- `billing_mode` (opcional, padrão: `"PAY_PER_REQUEST"`): modo de cobrança da tabela:
  - `"PAY_PER_REQUEST"` – on-demand (sem provisionar capacidade)
  - `"PROVISIONED"` – capacidade provisionada

- `read_capacity_units` (opcional, padrão: `5`): capacidade de leitura, usado apenas se `billing_mode = "PROVISIONED"`.  
- `write_capacity_units` (opcional, padrão: `5`): capacidade de escrita, usado apenas se `billing_mode = "PROVISIONED"`.

**Comportamento**

- Monta a definição de chave com:
  - chave de partição (sempre obrigatória)
  - sort key opcional (se informada)
- Usa `dynamodb.create_table(...)` com:
  - `TableName`
  - `AttributeDefinitions`
  - `KeySchema`
  - `BillingMode`
  - `ProvisionedThroughput` (apenas se `billing_mode = "PROVISIONED"`)
- Em LocalStack a tabela normalmente fica disponível imediatamente; em AWS real o status inicial pode ser `"CREATING"`.

**Exemplo – tabela só com chave de partição**

```bash
curl -X POST "http://localhost:8000/v1/dynamodb/tables" \
  -H "Content-Type: application/json" \
  -d '{
        "table_name": "MinhaTabela",
        "partition_key_name": "id",
        "partition_key_type": "S"
      }'
```

**Exemplo – tabela com partição + sort key, modo PROVISIONED**

```bash
curl -X POST "http://localhost:8000/v1/dynamodb/tables" \
  -H "Content-Type: application/json" \
  -d '{
        "table_name": "Pedidos",
        "partition_key_name": "cliente_id",
        "partition_key_type": "S",
        "sort_key_name": "pedido_id",
        "sort_key_type": "S",
        "billing_mode": "PROVISIONED",
        "read_capacity_units": 5,
        "write_capacity_units": 5
      }'
```

**Resposta (exemplo)**

```json
{
  "table_name": "Pedidos",
  "table_status": "ACTIVE",
  "table_arn": "arn:aws:dynamodb:us-east-1:000000000000:table/Pedidos",
  "billing_mode": "PROVISIONED"
}
```
---

#### 4. Criar ou atualizar item em uma tabela DynamoDB

```http
POST /v1/dynamodb/item?table_name=<nome_da_tabela>
```

**Query params**

- `table_name` (obrigatório): nome da tabela DynamoDB.

**Body (JSON)**

- `item` (obrigatório): objeto JSON representando o item completo a ser salvo na tabela.  
  > As chaves definidas no schema da tabela (partition key e sort key, se houver) devem estar presentes neste objeto.

**Comportamento**

- Realiza a operação `put_item` na tabela DynamoDB informada.
- Se o item já existir (mesma chave primária), ele será substituído.
- Se não existir, será criado.
- Valida se o campo `item` está presente e é um objeto.

**Exemplo**

```bash
curl -X POST "http://localhost:8000/v1/dynamodb/item?table_name=MinhaTabela" \
  -H "Content-Type: application/json" \
  -d '{
        "item": {
          "id": "1",
          "name": "Item 1"
        }
      }'
```

**Resposta (exemplo)**

```json
{
  "table_name": "MinhaTabela",
  "item": {
    "id": "1",
    "name": "Item 1"
  }
}
```

**Códigos de resposta**

- `201 Created`: Item salvo com sucesso.
- `400 Bad Request`: Corpo ausente ou inválido, campo `item` ausente ou com tipo inválido.
- `500 Internal Server Error`: Erro ao acessar o DynamoDB.

---

### 📮 SQS

#### 1. Enviar mensagem para uma fila (por nome)

```http
POST /v1/sqs/send?queue_name=<nome_da_fila>
```

**Query params**

- `queue_name` (obrigatório): nome da fila SQS.

**Body (JSON)**

- `message` (obrigatório): conteúdo da mensagem.  
- `delay_seconds` (opcional): atraso em segundos.  
- `attributes` (opcional): atributos no formato do SQS.

**Exemplo**

```bash
    curl -X POST "http://localhost:8000/v1/sqs/send?queue_name=minha-fila" \
      -H "Content-Type: application/json" \
      -d '{
            "message": "Olá SQS!",
            "delay_seconds": 0
          }'
```

**Resposta (exemplo)**

```json
{
  "message_id": "1234-5678",
  "queue_name": "minha-fila"
}
```

---

#### 2. Receber mensagens de uma fila

```http
GET /v1/sqs/messages
```

**Query params**

- `queue_name` (obrigatório): nome da fila SQS.  
- `max_number` (opcional, padrão: `1`, máx: `10`): quantidade máxima de mensagens.  
- `wait_time_seconds` (opcional, padrão: `0`, máx: `20`): long polling.  

> Observação: este endpoint **não apaga** as mensagens da fila, apenas as lê.  
> A deleção é feita por endpoints específicos (veja abaixo).

**Exemplo**

```bash
  curl "http://localhost:8000/v1/sqs/messages?queue_name=minha-fila&max_number=5"
```

**Resposta (exemplo)**

```json
{
  "queue_name": "minha-fila",
  "messages": [
    {
      "MessageId": "1234-5678",
      "ReceiptHandle": "AQEB...",
      "Body": "conteúdo da mensagem",
      "Attributes": {},
      "MessageAttributes": {}
    }
  ]
}
```

---

#### 3. Listar filas

```http
GET /v1/sqs/queues
```

**Query params**

- `prefix` (opcional): prefixo para filtrar nomes de filas (`QueueNamePrefix`).

**Exemplo**

```bash
  curl "http://localhost:8000/v1/sqs/queues?prefix=minha-"
```

**Resposta (exemplo)**

```json
{
  "queue_urls": [
    "http://localhost:4566/000000000000/minha-fila",
    "http://localhost:4566/000000000000/minha-outra-fila"
  ]
}
```

---

#### 4. Deletar uma mensagem específica da fila

```http
DELETE /v1/sqs/messages
```

**Query params**

- `queue_name` (obrigatório): nome da fila SQS.  
- `receipt_handle` (obrigatório): `ReceiptHandle` da mensagem retornado pelo SQS.  

**Exemplo**

```bash
    curl -X DELETE \
      "http://localhost:8000/v1/sqs/messages?queue_name=minha-fila&receipt_handle=AQEB..."
```

**Resposta (exemplo)**

```json
{
  "queue_name": "minha-fila",
  "receipt_handle": "AQEB...",
  "deleted": true
}
```

---

#### 5. Deletar todas as mensagens da fila (purge)

```http
DELETE /v1/sqs/messages/all
```

**Query params**

- `queue_name` (obrigatório): nome da fila SQS.

> Observações:
> - Usa a operação `PurgeQueue` do SQS.
> - Pode ser chamada no máximo **1 vez a cada 60 segundos**.
> - A remoção é **assíncrona**: as mensagens podem levar alguns segundos para sumir.

**Exemplo**

```bash
  curl -X DELETE "http://localhost:8000/v1/sqs/messages/all?queue_name=minha-fila"
```

**Resposta (exemplo)**

```json
{
  "queue_name": "minha-fila",
  "purged": true,
  "note": "Purge solicitado; operação é assincrona no SQS."
}
```

#### 6. Criar fila SQS

```http
POST /v1/sqs/queues
```

**Body (JSON)**

- `queue_name` (obrigatório): nome da fila SQS a ser criada.  
- `attributes` (opcional): mapa de atributos da fila aceitos pelo SQS, por exemplo:
  - `VisibilityTimeout` (segundos)
  - `MessageRetentionPeriod` (segundos)
  - `ReceiveMessageWaitTimeSeconds` (segundos)
  - `FifoQueue` (`"true"`/`"false"`)
  - `ContentBasedDeduplication` (`"true"`/`"false"`)

> Todos os valores de `attributes` devem ser **strings**, conforme a API do SQS.

**Comportamento**

- Usa `sqs.create_queue(QueueName=..., Attributes=...)`.  
- A operação é **idempotente**: se a fila já existir, o SQS retorna a fila existente.  
- Após criar (ou reutilizar) a fila, o serviço busca o ARN via `get_queue_attributes` e retorna `queue_url` e `queue_arn`.

**Exemplo**

```bash
curl -X POST "http://localhost:8000/v1/sqs/queues" \
  -H "Content-Type: application/json" \
  -d '{
        "queue_name": "minha-fila",
        "attributes": {
          "VisibilityTimeout": "30",
          "MessageRetentionPeriod": "86400"
        }
      }'
```

**Resposta (exemplo)**

```json
{
  "queue_name": "minha-fila",
  "queue_url": "http://localhost:4566/000000000000/minha-fila",
  "queue_arn": "arn:aws:sqs:us-east-1:000000000000:minha-fila"
}
```

---

### 📢 SNS

#### 1. Criar tópico

```http
POST /v1/sns/topics
```

**Body (JSON)**

- `name` (obrigatório): nome lógico do tópico.

**Exemplo**

```bash
    curl -X POST "http://localhost:8000/v1/sns/topics" \
      -H "Content-Type: application/json" \
      -d '{ "name": "meu-topico" }'
```

**Resposta (exemplo)**

```json
{
  "name": "meu-topico",
  "topic_arn": "arn:aws:sns:us-east-1:000000000000:meu-topico"
}
```

---

#### 2. Publicar mensagem em tópico (por nome)

```http
POST /v1/sns/publish?topic_name=<nome_do_topico>
```

**Query params**

- `topic_name` (obrigatório): nome lógico do tópico (última parte do ARN).

**Body (JSON)**

- `message` (obrigatório): conteúdo da mensagem.  
- `subject` (opcional): assunto.  
- `attributes` (opcional): atributos no formato do SNS.  

**Exemplo**

```bash
    curl -X POST "http://localhost:8000/v1/sns/publish?topic_name=meu-topico" \
      -H "Content-Type: application/json" \
      -d '{
            "message": "Olá SNS!",
            "subject": "Teste"
          }'
```

**Resposta (exemplo)**

```json
{
  "message_id": "abcd-1234",
  "topic_arn": "arn:aws:sns:us-east-1:000000000000:meu-topico",
  "topic_name": "meu-topico"
}
```

---

#### 3. Listar tópicos

```http
GET /v1/sns/topics
```

**Exemplo**

```bash
  curl "http://localhost:8000/v1/sns/topics"
```

**Resposta (exemplo)**

```json
{
  "topics": [
    {
      "topic_arn": "arn:aws:sns:us-east-1:000000000000:meu-topico",
      "name": "meu-topico"
    }
  ]
}
```

---

#### 4. Criar subscription (SNS → SQS ou SNS → Lambda)

```http
POST /v1/sns/subscriptions
```

**Body (JSON)**

- `topic_name` (opcional): nome lógico do tópico SNS (última parte do ARN).
- `topic_arn` (opcional): ARN completo do tópico SNS.  
  > É obrigatório informar **`topic_name`** ou **`topic_arn`**.

- `type` (obrigatório): tipo de destino da subscription:
  - `"sqs"` para fila SQS
  - `"lambda"` para função Lambda

- Para `type = "sqs"`:
  - `queue_name` (opcional): nome da fila SQS.
  - `queue_arn` (opcional): ARN completo da fila SQS.  
    > É obrigatório informar **`queue_name`** ou **`queue_arn`**.

- Para `type = "lambda"`:
  - `lambda_arn` (obrigatório): ARN da função Lambda.

**Comportamento**

- Se for enviado `topic_name`, o serviço resolve o `topic_arn` usando `list_topics`.
- Se for enviado `queue_name` (para `type="sqs"`), o serviço resolve o `queue_arn` usando `get_queue_url` + `get_queue_attributes`.
- Para `type="sqs"`, a subscription é criada com o atributo:
  ```json
  { "RawMessageDelivery": "true" }
  ```
  para entregar a mensagem “crua” na fila (útil em LocalStack).
- Para `type="lambda"`, é usado `Protocol="lambda"` e `Endpoint=lambda_arn`.  
  Em AWS real, normalmente é necessário adicionar permissões na Lambda (não tratado aqui).

**Resposta (exemplo)**

```json
{
  "subscription_arn": "arn:aws:sns:us-east-1:000000000000:meu-topico:abcd-1234",
  "topic_arn": "arn:aws:sns:us-east-1:000000000000:meu-topico",
  "protocol": "sqs",
  "endpoint": "arn:aws:sqs:us-east-1:000000000000:minha-fila"
}
```

**Exemplo – criar subscription SNS → SQS usando nomes**

```bash
    curl -X POST "http://localhost:8000/v1/sns/subscriptions" \
      -H "Content-Type: application/json" \
      -d '{
        "topic_name": "meu-topico",
        "type": "sqs",
        "queue_name": "minha-fila"
      }'
```

**Exemplo – criar subscription SNS → Lambda usando ARN**

```bash
    curl -X POST "http://localhost:8000/v1/sns/subscriptions" \
      -H "Content-Type: application/json" \
      -d '{
        "topic_name": "meu-topico",
        "type": "lambda",
        "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:minha-funcao"
      }'
```

---

## 📁 Estrutura de Pastas

```text
.
├── app
│   ├── main.py              # Ponto de entrada Flask (registra blueprints)
│   ├── routes
│   │   ├── dynamodb.py      # Endpoints DynamoDB
│   │   ├── sns.py           # Endpoints SNS
│   │   └── sqs.py           # Endpoints SQS
│   └── utils
│       ├── aws.py           # Factories de clientes boto3 (SNS/SQS/DynamoDB)
│       └── http.py          # Helpers HTTP (validação de body/query)
├── run-local-stack.sh       # Script para subir o LocalStack
├── requirements.txt
└── README.md
```

---

## ✅ Testes

Se você tiver testes automatizados, rode, por exemplo:

```bash
pytest
# ou
python -m pytest
```

---

## 🧪 Exemplo de Fluxo de Uso

1. 🐳 Subir o LocalStack com `./run-local-stack.sh`.  
2. 🔧 Exportar variáveis de ambiente de AWS/LocalStack (endpoints e região).  
3. 🚀 Subir o serviço Flask (`flask run ...`).  
4. 📚 Criar tabela no DynamoDB (via CLI/AWS SDK ou LocalStack).  
5. 📮 Criar fila SQS e 📢 criar tópico SNS via endpoints REST.  
6. 📤 Enviar mensagens para SQS ou publicar em tópicos SNS usando **nome** (a API resolve ARN/URL ou QueueUrl).  
7. 📥 Ler mensagens de SQS com `/v1/sqs/messages`.  
8. 🗑️ Deletar mensagens específicas (`DELETE /v1/sqs/messages`) ou limpar toda a fila (`DELETE /v1/sqs/messages/all`).  
9. 📚 Ler itens de tabelas DynamoDB com `/v1/dynamodb/all` e `/v1/dynamodb/item`.  

---

## 📄 Licença

Adicione aqui a licença do projeto (MIT, Apache 2.0, etc.), se houver.