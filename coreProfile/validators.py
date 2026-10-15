import os

from rest_framework import serializers

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image(file, max_mb=2):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise serializers.ValidationError("Only .jpg, .jpeg, .png and .webp images are allowed.")
    if file.size > max_mb * 1024 * 1024:
        raise serializers.ValidationError(f"Image size must not exceed {max_mb} MB.")
    return file


def validate_pdf(file, max_mb=5):
    ext = os.path.splitext(file.name)[1].lower()
    if ext != ".pdf":
        raise serializers.ValidationError("Only PDF files are allowed.")
    if file.size > max_mb * 1024 * 1024:
        raise serializers.ValidationError(f"File size must not exceed {max_mb} MB.")
    return file