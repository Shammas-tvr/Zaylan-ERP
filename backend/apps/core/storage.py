"""Presigned Cloudflare R2 uploads. Object keys are stored on products and items; file bytes are not."""

import uuid
from pathlib import Path

from django.conf import settings
from rest_framework.exceptions import ValidationError

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
PURPOSES = {"product", "item"}


def r2_configured() -> bool:
    return bool(
        settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET
        and settings.R2_ENDPOINT
    )


def image_url(object_key: str) -> str | None:
    if not object_key:
        return None
    public = (settings.R2_PUBLIC_BASE_URL or "").rstrip("/")
    if public:
        return f"{public}/{object_key}"
    if not r2_configured():
        return None
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": object_key},
        ExpiresIn=3600,
    )


def create_image_upload(*, organization_id, purpose: str, content_type: str, filename: str) -> dict:
    if purpose not in PURPOSES:
        raise ValidationError({"purpose": ["Choose a product or inventory item image."]})
    extension = ALLOWED_TYPES.get((content_type or "").lower())
    if extension is None:
        raise ValidationError({"content_type": ["Use a JPEG, PNG, or WebP image."]})
    if not r2_configured():
        raise ValidationError({"image": ["Image storage is not configured. Set the R2 settings on the server."]})
    suffix = Path(filename or "").suffix.lower()
    if suffix and suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValidationError({"filename": ["Use a JPEG, PNG, or WebP file."]})
    key = f"org/{organization_id}/{purpose}/{uuid.uuid4().hex}{extension}"
    upload_url = _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=600,
    )
    return {
        "object_key": key,
        "upload_url": upload_url,
        "headers": {"Content-Type": content_type},
        "max_bytes": settings.R2_IMAGE_MAX_BYTES,
    }


def owned_image_key(organization_id, key: str) -> str:
    cleaned = (key or "").strip()
    if not cleaned:
        return ""
    prefix = f"org/{organization_id}/"
    if not cleaned.startswith(prefix) or ".." in cleaned:
        raise ValidationError({"image_key": ["That image does not belong to this brand."]})
    return cleaned


def _client():
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
