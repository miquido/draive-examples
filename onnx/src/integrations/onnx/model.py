import gc
from asyncio import to_thread
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as onnx
from draive import as_dict, as_list, ctx

from integrations.onnx.types import ONNXExcetion, ONNXExecutionProvider, ONNXSessionOptions

__all__ = ("ONNXModel",)


class ONNXModel:
    __slots__ = (
        "_execution_provider",
        "_model_path",
        "_session",
        "_session_options",
    )

    def __init__(
        self,
        model_path: Path | str,
        /,
        *,
        execution_provider: ONNXExecutionProvider,
        session_options: ONNXSessionOptions | None = None,
    ) -> None:
        self._model_path: Path | str = model_path
        self._execution_provider: ONNXExecutionProvider = execution_provider
        self._session_options: ONNXSessionOptions
        if session_options is not None:
            self._session_options = session_options

        else:
            default_options = onnx.SessionOptions()
            default_options.graph_optimization_level = onnx.GraphOptimizationLevel.ORT_ENABLE_ALL
            default_options.execution_mode = onnx.ExecutionMode.ORT_SEQUENTIAL
            default_options.log_severity_level = 1 if __debug__ else 3
            self._session_options = default_options

        self._session: onnx.InferenceSession

    @property
    def input_names(self) -> Sequence[str]:
        return tuple(element.name for element in self._session.get_inputs())

    @property
    def output_names(self) -> Sequence[str]:
        return tuple(element.name for element in self._session.get_outputs())

    def _initialize_session(self) -> None:
        if hasattr(self, "_session"):
            return  # already initialized

        ctx.log_info(f"Loading onnx model from {self._model_path}")

        path: Path
        match self._model_path:
            case str() as path_str:
                path = Path(path_str)

            case Path() as model_path:
                path = model_path

        if not path.exists():
            raise FileNotFoundError(f"onnx model not found at {path}")

        try:
            self._session = onnx.InferenceSession(
                str(path),
                sess_options=self._session_options,
                providers=[self._execution_provider],
            )

        except Exception as exc:
            raise ONNXExcetion(f"onnx model session creation failed: {exc}") from exc

    def _deinitialize_session(self) -> None:
        if not hasattr(self, "_session"):
            return  # already deinitialized
        del self._session
        gc.collect()

    async def run(
        self,
        *,
        output_names: Sequence[Any] | None = None,
        input_feed: Mapping[str, Any] | None = None,
        run_options: onnx.RunOptions | None = None,
    ) -> Sequence[np.ndarray | Any]:
        ctx.log_debug(f"Running onnx model {self._model_path}")
        return await to_thread(
            self._run,
            output_names=output_names,
            input_feed=input_feed,
            run_options=run_options,
        )

    def _run(
        self,
        *,
        output_names: Sequence[Any] | None = None,
        input_feed: Mapping[str, Any] | None = None,
        run_options: onnx.RunOptions | None = None,
    ) -> Sequence[np.ndarray | Any]:
        try:
            return self._session.run(
                output_names=as_list(output_names),
                input_feed=as_dict(input_feed),
                run_options=run_options,
            )

        except Exception as exc:
            raise ONNXExcetion(f"onnx model run failed: {exc}") from exc
