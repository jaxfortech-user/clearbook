import boto3
import json
from app.core.config import settings


sqs_client = boto3.client(
    "sqs",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


def queue_document_for_processing(document_id: str, client_id: str, s3_key: str):
    message = {
        "document_id": document_id,
        "client_id": client_id,
        "s3_key": s3_key,
    }
    sqs_client.send_message(
        QueueUrl=settings.SQS_QUEUE_URL,
        MessageBody=json.dumps(message),
    )