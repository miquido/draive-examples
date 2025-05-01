from typing import Any, Literal

import onnxruntime as onnx

__all__ = (
    "ONNXExcetion",
    "ONNXExecutionProvider",
    "ONNXSessionOptions",
)


class ONNXExcetion(Exception):
    pass


type ONNXExecutionProviderName = (
    Literal[
        "ROCMExecutionProvider",
        "CUDAExecutionProvider",
        "CoreMLExecutionProvider",
        "CPUExecutionProvider",
        "AzureExecutionProvider",
    ]
    | str
)
type ONNXExecutionProvider = (
    ONNXExecutionProviderName | tuple[ONNXExecutionProviderName, dict[str, Any]]
)
type ONNXSessionOptions = onnx.SessionOptions
