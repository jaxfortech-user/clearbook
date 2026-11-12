import boto3
import uuid
from app.core.config import settings


s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


def upload_file_to_s3(file_bytes: bytes, file_name: str, client_id: str, content_type: str) -> str:
    ext = file_name.rsplit(".", 1)[-1].lower()
    s3_key = f"documents/{client_id}/{uuid.uuid4()}.{ext}"
    s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return s3_key


def generate_presigned_url(s3_key: str, expiry: int = 3600) -> str:
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expiry,
    )