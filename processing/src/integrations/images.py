from io import BytesIO

from PIL import Image

__all__ = ["normalized_image"]

MAX_IMAGE_BYTES = 3 * 1000 * 1000  # it used to be 5MB but having a margin by rounding
MAX_IMAGE_SIZE = (2048, 2048)


def normalized_image(
    image: Image.Image | bytes,
    /,
) -> bytes:
    image_data: bytes
    pil_image: Image.Image
    match image:
        case bytes() as data:
            pil_image = Image.open(BytesIO(data))
            if pil_image.mode == "RGBA":
                pil_image = pil_image.convert("RGB")

            image_data = data

        case image:
            if image.mode == "RGBA":
                pil_image = image.convert("RGB")

            else:
                pil_image = image

            output = BytesIO()
            pil_image.save(output, format="PNG")
            image_data = output.getvalue()

    if pil_image.size[0] > MAX_IMAGE_SIZE[0] or pil_image.size[1] > MAX_IMAGE_SIZE[1]:
        ratio: float = min(
            MAX_IMAGE_SIZE[0] / pil_image.size[0],
            MAX_IMAGE_SIZE[1] / pil_image.size[1],
        )

        pil_image = pil_image.resize(
            (
                int(pil_image.size[0] * ratio),
                int(pil_image.size[1] * ratio),
            ),
            Image.Resampling.LANCZOS,
        )

    while len(image_data) > MAX_IMAGE_BYTES:
        ratio = (MAX_IMAGE_BYTES / len(image_data)) ** 0.5

        pil_image = pil_image.resize(
            (
                int(pil_image.size[0] * ratio),
                int(pil_image.size[1] * ratio),
            ),
            Image.Resampling.LANCZOS,
        )

        output = BytesIO()
        pil_image.save(output, format="PNG")
        image_data = output.getvalue()

    return image_data
