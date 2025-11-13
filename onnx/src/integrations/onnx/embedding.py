import json
from asyncio import Lock, to_thread
from collections.abc import Callable, Sequence
from itertools import chain
from pathlib import Path
from types import TracebackType
from typing import Any, cast, override

import numpy as np
from draive import DataModel, Embedded, State, TextEmbedding, as_list
from haiway import ctx
from tokenizers import AddedToken, Encoding, Tokenizer

from integrations.onnx.model import ONNXModel
from integrations.onnx.types import (
    ONNXExecutionProvider,
    ONNXSessionOptions,  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
)

__all__ = (
    "ONNXEmbeddingConfig",
    "ONNXEmbeddingModel",
)


type NumpyArray = np.ndarray


class ONNXEmbeddingConfig(State):
    batch_size: int = 32


class ONNXEmbeddingModel(ONNXModel):
    __slots__ = (
        "_session_lock",
        "_tokenizer",
        "_tokenizer_path",
    )

    def __init__(
        self,
        model_path: Path | str,
        /,
        *,
        tokenizer_path: Path | str | None = None,
        execution_provider: ONNXExecutionProvider,
        session_options: ONNXSessionOptions | None = None,  # pyright: ignore[reportUnknownParameterType]
    ) -> None:
        super().__init__(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
            model_path,
            execution_provider=execution_provider,
            session_options=session_options,
        )

        self._tokenizer_path: Path
        match tokenizer_path:
            case None:
                match model_path:
                    case str() as path_str:
                        self._tokenizer_path = Path(path_str).parent

                    case path:
                        self._tokenizer_path = path.parent

            case str() as path_str:
                self._tokenizer_path = Path(path_str)

            case path:
                self._tokenizer_path = path

        self._tokenizer: Tokenizer
        self._session_lock: Lock = Lock()

    @override
    def _initialize_session(self) -> None:
        super()._initialize_session()
        self._tokenizer = _load_tokenizer(self._tokenizer_path)

    async def __aenter__(self) -> TextEmbedding:
        async with self._session_lock:
            self._initialize_session()

            async def create_texts_embedding[Value: DataModel | State](
                values: Sequence[Value] | Sequence[str],
                /,
                attribute: Callable[[Value], str] | None = None,
                *,
                config: ONNXEmbeddingConfig | None = None,
                **extra: Any,
            ) -> Sequence[Embedded[Value]] | Sequence[Embedded[str]]:
                embedding_config: ONNXEmbeddingConfig = config or ctx.state(ONNXEmbeddingConfig)
                attributes: list[str]
                if attribute is None:
                    attributes = cast(list[str], as_list(values))

                else:
                    attributes = [attribute(cast(Value, value)) for value in values]

                assert all(isinstance(element, str) for element in attributes)  # nosec: B101

                embeddings: Sequence[Sequence[float]] = await self.embed_texts(
                    attributes,
                    batch_size=embedding_config.batch_size,
                )
                return cast(
                    Sequence[Embedded[Value]] | Sequence[Embedded[str]],
                    [
                        Embedded(
                            value=value,
                            vector=embedding,
                        )
                        for value, embedding in zip(
                            values,
                            embeddings,
                            strict=True,
                        )
                    ],
                )

            return TextEmbedding(embedding=create_texts_embedding)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._deinitialize_session()

    async def embed_texts(
        self,
        texts: Sequence[str],
        /,
        *,
        batch_size: int,
    ) -> Sequence[Sequence[float]]:
        async with ctx.scope("text_embedding"):
            async with self._session_lock:
                return await to_thread(
                    self._embed_texts,
                    texts,
                    batch_size=batch_size,
                )

    def _embed_texts(
        self,
        texts: Sequence[str],
        /,
        *,
        batch_size: int,
    ) -> Sequence[Sequence[float]]:
        return tuple(
            chain.from_iterable(
                self._embed_texts_batch(texts[idx : idx + batch_size])
                for idx in range(0, len(texts), batch_size)
            )
        )

    def _embed_texts_batch(
        self,
        texts: Sequence[str],
        /,
    ) -> Sequence[Sequence[float]]:
        try:
            # Encode all texts in the batch
            encodings: list[Encoding] = self._tokenizer.encode_batch(texts)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            # Prepare batch inputs
            input_ids = np.array([encoding.ids for encoding in encodings])  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
            onnx_input: dict[str, np.ndarray] = {
                "input_ids": np.array(input_ids, dtype=np.int64),
            }
            # Add attention mask if needed
            if "attention_mask" in self.input_names:
                onnx_input["attention_mask"] = np.array(
                    np.array([encoding.attention_mask for encoding in encodings]),  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
                    dtype=np.int64,
                )
            # Add token type ids if needed
            if "token_type_ids" in self.input_names:
                onnx_input["token_type_ids"] = np.zeros_like(input_ids, dtype=np.int64)
            # Run the model
            model_output: Sequence[Any] = self._run(input_feed=onnx_input)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
            embeddings = model_output[0]
            # Process embeddings based on their shape
            if embeddings.ndim == 3:  # (batch_size, seq_len, embedding_dim)  # noqa: PLR2004
                processed_embeddings = embeddings[:, 0]  # Take the [CLS] token embedding

            elif embeddings.ndim == 2:  # (batch_size, embedding_dim)  # noqa: PLR2004
                processed_embeddings = embeddings

            else:
                raise ValueError(f"Unsupported embedding shape: {embeddings.shape}")

            return tuple(
                embedding.tolist() for embedding in processed_embeddings.astype(np.float32)
            )

        except Exception as e:
            raise RuntimeError(f"Text embedding failed: {e}") from e


def _load_tokenizer_special_tokens(model_dir: Path) -> dict[str, Any] | None:
    tokens_map_path = model_dir / "special_tokens_map.json"
    if not tokens_map_path.exists():
        return None

    with open(str(tokens_map_path)) as file:
        tokens_map: dict[str, Any] = json.load(file)
        return tokens_map


def _load_pad_token_id(model_dir: Path) -> int:
    config_path = model_dir / "config.json"
    if not config_path.exists():
        raise ValueError(f"Missing config.json at {model_dir}")

    with open(str(config_path)) as file:
        config: dict[str, Any] = json.load(file)
        return config.get("pad_token_id", 0)


def _load_tokenizer_config(model_dir: Path) -> tuple[int, str]:
    config_path = model_dir / "tokenizer_config.json"
    if not config_path.exists():
        raise ValueError(f"Missing tokenizer_config.json at {model_dir}")

    with open(str(config_path)) as file:
        tokenizer_config: dict[str, Any] = json.load(file)
        if "model_max_length" not in tokenizer_config:
            return (
                tokenizer_config["max_length"],
                tokenizer_config["pad_token"],
            )

        elif "max_length" not in tokenizer_config:
            return (
                tokenizer_config["model_max_length"],
                tokenizer_config["pad_token"],
            )

        else:
            return (
                min(tokenizer_config["model_max_length"], tokenizer_config["max_length"]),
                tokenizer_config["pad_token"],
            )


def _load_tokenizer(model_dir: Path) -> Tokenizer:
    tokenizer_path = model_dir / "tokenizer.json"
    if not tokenizer_path.exists():
        raise ValueError(f"Missing tokenizer.json at {model_dir}")

    tokenizer = Tokenizer.from_file(str(tokenizer_path))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]

    max_length, pad_token = _load_tokenizer_config(model_dir)
    tokenizer.enable_truncation(max_length=max_length)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
    pad_token_id = _load_pad_token_id(model_dir)
    tokenizer.enable_padding(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
        pad_id=pad_token_id,
        pad_token=pad_token,
    )

    if tokens_map := _load_tokenizer_special_tokens(model_dir):
        for token in tokens_map.values():
            if isinstance(token, str):
                tokenizer.add_special_tokens([token])  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]

            elif isinstance(token, dict):
                tokenizer.add_special_tokens([AddedToken(**token)])  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]

    return tokenizer  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
