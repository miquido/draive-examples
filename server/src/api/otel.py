from draive.opentelemetry import OpenTelemetry

from api.config import OTEL_ENVIRONMENT, OTEL_EXPORTER_ENDPOINT, OTEL_SERVICE_INSTANCE_ID, VERSION

__all__ = ("setup_telemetry",)


def setup_telemetry() -> bool:
    if endpoint := OTEL_EXPORTER_ENDPOINT:
        OpenTelemetry.configure(
            service="api",
            version=VERSION,
            environment=OTEL_ENVIRONMENT,
            otlp_endpoint=endpoint,
            insecure=True,
            export_interval_millis=5000,
            attributes={
                "service": "api",
                "component": "ai",
                "service.instance.id": OTEL_SERVICE_INSTANCE_ID,
            },
        )

        return True

    return False
