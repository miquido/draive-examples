from io import BytesIO

from PIL import Image

__all__ = ["normalized_image"]

MAX_IMAGE_BYTES = 5 * 1000 * 1000  # it used to be 5MB but having a margin by rounding to 1k
MAX_IMAGE_SIZE = (2048, 2048)  # OpenAI api resizes images to this size anyways


def normalized_image(
    image_data: bytes,
    /,
) -> bytes:
    image = Image.open(BytesIO(image_data))

    if image.size[0] > MAX_IMAGE_SIZE[0] or image.size[1] > MAX_IMAGE_SIZE[1]:
        ratio: float = min(
            MAX_IMAGE_SIZE[0] / image.size[0],
            MAX_IMAGE_SIZE[1] / image.size[1],
        )

        image = image.resize(
            (
                int(image.size[0] * ratio),
                int(image.size[1] * ratio),
            ),
            Image.Resampling.LANCZOS,
        )

    while len(image_data) > MAX_IMAGE_BYTES:
        ratio = (MAX_IMAGE_BYTES / len(image_data)) ** 0.5

        image = image.resize(
            (
                int(image.size[0] * ratio),
                int(image.size[1] * ratio),
            ),
            Image.Resampling.LANCZOS,
        )

        output = BytesIO()
        image.save(output, format="PNG")
        image_data = output.getvalue()

    return image_data
