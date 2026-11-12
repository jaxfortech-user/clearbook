import json
import boto3
import time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.document import Document
from app.services.textract_service import extract_text_from_s3
from app.services.ai_extraction_service import extract_structured_data, extract_from_image_with_vision
from app.services.s3_service import s3_client

# Sync engine for worker (not async)
sync_engine = create_engine(
    settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
)

sqs = boto3.client(
    "sqs",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)

CONFIDENCE_THRESHOLD = 80.0


def process_document(document_id: str, s3_key: str):
    with Session(sync_engine) as db:
        doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
        if not doc:
            print(f"Document {document_id} not found")
            return

        # Update status to processing
        doc.status = "processing"
        db.commit()

        try:
            is_image = doc.file_type in ("jpg", "jpeg", "png", "tiff")

            if is_image:
                # Get image from S3
                obj = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
                image_bytes = obj["Body"].read()
                mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "tiff": "image/tiff"}
                mime_type = mime_map.get(doc.file_type, "image/jpeg")

                # Try Textract first
                textract_result = extract_text_from_s3(s3_key)
                confidence = textract_result["avg_confidence"]
                doc.is_handwritten = confidence < CONFIDENCE_THRESHOLD

                if confidence >= CONFIDENCE_THRESHOLD:
                    extracted = extract_structured_data(textract_result["raw_text"], textract_result["forms"])
                else:
                    # Fallback to GPT-4o Vision for handwritten
                    print(f"Low confidence ({confidence}%), using GPT-4o Vision fallback")
                    extracted = extract_from_image_with_vision(image_bytes, mime_type)
            else:
                # PDF — use Textract
                textract_result = extract_text_from_s3(s3_key)
                confidence = textract_result["avg_confidence"]
                extracted = extract_structured_data(textract_result["raw_text"], textract_result["forms"])

            doc.extracted_data = extracted
            doc.confidence_score = confidence
            doc.document_type = extracted.get("document_type")
            doc.status = "extracted" if confidence >= CONFIDENCE_THRESHOLD else "review_required"
            db.commit()
            print(f"Document {document_id} processed. Status: {doc.status}, Confidence: {confidence}%")

        except Exception as e:
            doc.status = "failed"
            doc.notes = str(e)
            db.commit()
            print(f"Document {document_id} failed: {e}")


def run_worker():
    print("Clearbook AI Extraction Worker started...")
    while True:
        response = sqs.receive_message(
            QueueUrl=settings.SQS_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
        )
        messages = response.get("Messages", [])
        if not messages:
            continue

        for message in messages:
            body = json.loads(message["Body"])
            print(f"Processing: {body}")
            process_document(body["document_id"], body["s3_key"])
            sqs.delete_message(
                QueueUrl=settings.SQS_QUEUE_URL,
                ReceiptHandle=message["ReceiptHandle"],
            )


if __name__ == "__main__":
    run_worker()