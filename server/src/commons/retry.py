from draive import ModelRateLimit

__all__ = ("retry_delay",)


def retry_delay(
    attempt: int,
    exception: Exception,
) -> float:
    if isinstance(exception, ModelRateLimit):
        return exception.retry_after

    else:
        return 0.3 * attempt**2
