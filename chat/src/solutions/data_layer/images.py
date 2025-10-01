from io import BytesIO

from PIL import Image

__all__ = ["normalized_image"]

MAX_IMAGE_BYTES = 5 * 1000 * 1000  # it used to be 5MB but having a margin by rounding to 1k
MAX_IMAGE_SIZE = (2048, 2048)  # OpenAI api resizes images to this size anyways


def normalized_image(
    image_data: bytes,
    /,
) -> bytes:
    with Image.open(BytesIO(image_data)) as original:
        format_name = (original.format or "PNG").upper()
        mime_known = format_name in Image.MIME
        image = original.copy()

    if not mime_known:
        format_name = "PNG"
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

    if format_name == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    image_data = _encode_image(image, format_name)

    if image.size[0] > MAX_IMAGE_SIZE[0] or image.size[1] > MAX_IMAGE_SIZE[1]:
        ratio: float = min(
            MAX_IMAGE_SIZE[0] / image.size[0],
            MAX_IMAGE_SIZE[1] / image.size[1],
        )

        new_size = (
            max(1, int(image.size[0] * ratio)),
            max(1, int(image.size[1] * ratio)),
        )

        image = image.resize(new_size, Image.Resampling.LANCZOS)
        image_data = _encode_image(image, format_name)

    while len(image_data) > MAX_IMAGE_BYTES and min(image.size) > 1:
        ratio = (MAX_IMAGE_BYTES / len(image_data)) ** 0.5
        new_size = (
            max(1, int(image.size[0] * ratio)),
            max(1, int(image.size[1] * ratio)),
        )

        if new_size == image.size:
            new_size = (
                max(1, image.size[0] - 1),
                max(1, image.size[1] - 1),
            )

        image = image.resize(new_size, Image.Resampling.LANCZOS)
        image_data = _encode_image(image, format_name)

    return image_data


def _encode_image(image: Image.Image, format_name: str) -> bytes:
    buffer = BytesIO()
    save_image = image
    if format_name == "JPEG" and image.mode not in ("RGB", "L"):
        save_image = image.convert("RGB")

    save_kwargs: dict[str, int | bool] = {}
    if format_name == "JPEG":
        save_kwargs = {"quality": 85, "optimize": True}

    save_image.save(buffer, format=format_name, **save_kwargs)
    return buffer.getvalue()
