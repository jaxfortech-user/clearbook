import time
import boto3
from app.core.config import settings

textract_client = boto3.client(
    "textract",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


def extract_text_from_s3(s3_key: str) -> dict:
    # Start async job (supports multi-page PDFs)
    response = textract_client.start_document_analysis(
        DocumentLocation={
            "S3Object": {
                "Bucket": settings.S3_BUCKET_NAME,
                "Name": s3_key,
            }
        },
        FeatureTypes=["FORMS", "TABLES"],
    )
    job_id = response["JobId"]

    # Poll until complete
    while True:
        result = textract_client.get_document_analysis(JobId=job_id)
        status = result["JobStatus"]
        if status == "SUCCEEDED":
            break
        elif status == "FAILED":
            raise Exception(f"Textract job failed for {s3_key}")
        time.sleep(3)

    # Paginate through all results
    blocks = []
    blocks.extend(result.get("Blocks", []))
    next_token = result.get("NextToken")
    while next_token:
        page = textract_client.get_document_analysis(JobId=job_id, NextToken=next_token)
        blocks.extend(page.get("Blocks", []))
        next_token = page.get("NextToken")

    # Parse blocks
    raw_text = []
    forms = {}
    confidence_scores = []
    block_map = {b["Id"]: b for b in blocks}

    for block in blocks:
        confidence_scores.append(block.get("Confidence", 0))

        if block["BlockType"] == "LINE":
            raw_text.append(block.get("Text", ""))

        if block["BlockType"] == "KEY_VALUE_SET" and "KEY" in block.get("EntityTypes", []):
            key_text = ""
            value_text = ""
            for rel in block.get("Relationships", []):
                if rel["Type"] == "CHILD":
                    for child_id in rel["Ids"]:
                        b = block_map.get(child_id)
                        if b and b["BlockType"] == "WORD":
                            key_text += b.get("Text", "") + " "
                if rel["Type"] == "VALUE":
                    for val_id in rel["Ids"]:
                        val_block = block_map.get(val_id)
                        if val_block:
                            for r in val_block.get("Relationships", []):
                                if r["Type"] == "CHILD":
                                    for c in r["Ids"]:
                                        bb = block_map.get(c)
                                        if bb and bb["BlockType"] == "WORD":
                                            value_text += bb.get("Text", "") + " "
            if key_text.strip():
                forms[key_text.strip()] = value_text.strip()

    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

    return {
        "raw_text": "\n".join(raw_text),
        "forms": forms,
        "avg_confidence": round(avg_confidence, 2),
    }