"""Optional local-AI resource plugins used by the fixed Relay pipeline.

The plugins in this module never replace parser output, rule labels, offsets, or
provenance.  They add explainable metadata when their local package *and* model
cache are ready.  Each primary has a deterministic local fallback registered in
``registry.py`` so an offline installation is always usable.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from zyrelay.app.core.config import Settings, load_yaml
from zyrelay.app.models import BlockType

from .models import ResourceHealth, ResourceRequest, ResourceResponse


class LocalModelResource:
    """Common compatibility surface for Resource Plugins and v0.6 consumers."""

    resource_id = "local-model"
    resource_type = "model"
    version = "1.0.0"
    config_key = ""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _config(self) -> dict[str, Any]:
        return (
            load_yaml(self.settings.model_config)
            .get("models", {})
            .get(self.config_key, {})
        )

    def _cache_dir(self) -> Path:
        configured = Path(str(self._config().get("cache_dir", "model_cache")))
        # ``data/model_cache/...`` is portable between source checkouts and a
        # custom ZYRELAY_DATA_ROOT; never bind a model path in Python code.
        if configured.parts and configured.parts[0] == "data":
            configured = Path(*configured.parts[1:])
        return (
            configured
            if configured.is_absolute()
            else self.settings.data_root / configured
        )

    def available(self) -> bool:
        return self.health_check().available

    def health(self) -> ResourceHealth:
        return self.health_check()

    def metadata(self) -> dict[str, Any]:
        config = self._config()
        return {
            "plugin_name": self.resource_id,
            "model_version": str(config.get("model_version", self.version)),
            "model_id": config.get("model_id"),
            "cache_dir": str(self._cache_dir()),
            "enabled": bool(config.get("enabled", True)),
        }

    def _enabled(self) -> bool:
        return bool(self._config().get("enabled", True))

    def _health(
        self, package: str | None = None, files: tuple[str, ...] = ()
    ) -> ResourceHealth:
        if not self._enabled():
            return ResourceHealth(
                available=False, status="disabled", details=self.metadata()
            )
        missing = [name for name in files if not (self._cache_dir() / name).exists()]
        if missing:
            return ResourceHealth(
                available=False,
                status="model_not_cached",
                details={**self.metadata(), "missing_files": missing},
            )
        if package:
            try:
                __import__(package)
            except ImportError:
                return ResourceHealth(
                    available=False,
                    status="package_missing",
                    details={**self.metadata(), "package": package},
                )
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )


class FastTextLanguageResource(LocalModelResource):
    resource_id = "fasttext-language"
    resource_type = "language_detection"
    version = "1.0.0"
    config_key = "fasttext_language"

    def health_check(self) -> ResourceHealth:
        return self._health(
            "fasttext", (str(self._config().get("model_file", "lid.176.ftz")),)
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "language_detection"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        started = time.perf_counter()
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable", warnings=[health.status], metadata=health.details
            )
        import fasttext

        model = fasttext.load_model(
            str(self._cache_dir() / self._config().get("model_file", "lid.176.ftz"))
        )
        detected: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        for block in request.options.get("blocks", []):
            text = getattr(block, "text", "").replace("\n", " ").strip()
            if not text:
                continue
            try:
                labels, scores = model.predict(text[:1000], k=1)
                code = labels[0].removeprefix("__label__") if labels else "unknown"
                detected[getattr(block, "block_id", "")] = {
                    "language": _language_code(code),
                    "confidence": float(scores[0]) if scores else 0.0,
                }
            except Exception as exc:
                # Some fasttext wheels still call NumPy 1.x-only APIs.  Keep
                # the cached model installed and expose the deterministic local
                # script fallback instead of interrupting document processing.
                warnings.append(f"fastText prediction fallback: {exc}")
                detected[getattr(block, "block_id", "")] = _script_language(text)
        return ResourceResponse(
            status="completed",
            payload={"blocks": detected},
            warnings=warnings,
            metadata={
                **self.metadata(),
                "duration_ms": (time.perf_counter() - started) * 1000,
                **({"fallback": "script_heuristic"} if warnings else {}),
            },
        )


class HeuristicLanguageResource(LocalModelResource):
    resource_id = "heuristic-language"
    resource_type = "language_detection"
    version = "1.0.0"
    config_key = "heuristic_language"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "language_detection"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        values = {}
        for block in request.options.get("blocks", []):
            text = getattr(block, "text", "")
            values[getattr(block, "block_id", "")] = _script_language(text)
        return ResourceResponse(
            status="completed",
            payload={"blocks": values, "fallback": "script_heuristic"},
            metadata=self.metadata(),
        )


class MiniLMDocumentClassifierResource(LocalModelResource):
    resource_id = "minilm-document-classifier"
    resource_type = "document_classifier"
    version = "1.0.0"
    config_key = "minilm_classifier"

    def health_check(self) -> ResourceHealth:
        return self._health("transformers", ("config.json", "model.safetensors"))

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "document_classifier"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        """Classify by local MiniLM embeddings; no remote inference is attempted."""
        started = time.perf_counter()
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable", warnings=[health.status], metadata=health.details
            )
        text = str(request.options.get("text", ""))[:4000]
        labels = self._config().get(
            "labels", ["contract", "invoice", "code_specification", "general_document"]
        )
        if not text:
            return ResourceResponse(
                status="completed",
                payload={"label": "general_document", "confidence": 0.0},
                metadata=self.metadata(),
            )
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                str(self._cache_dir()), local_files_only=True
            )
            model = AutoModel.from_pretrained(
                str(self._cache_dir()), local_files_only=True
            )
            model.eval()
            prompts = [
                text,
                *[f"This document is a {label.replace('_', ' ')}." for label in labels],
            ]
            encoded = tokenizer(
                prompts,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.no_grad():
                output = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1)
            embedding = (output * mask).sum(1) / mask.sum(1).clamp(min=1)
            scores = torch.nn.functional.cosine_similarity(
                embedding[0:1], embedding[1:]
            ).tolist()
            best = max(range(len(labels)), key=lambda index: scores[index])
            payload = {
                "label": labels[best],
                "confidence": round(float((scores[best] + 1) / 2), 4),
                "scores": dict(zip(labels, scores)),
            }
        except Exception as exc:
            # A cached model can still be incompatible with a platform's torch.
            return ResourceResponse(
                status="partial",
                payload=_classify_keywords(text),
                warnings=[f"MiniLM inference fallback: {exc}"],
                metadata={**self.metadata(), "fallback": "keyword"},
            )
        return ResourceResponse(
            status="completed",
            payload=payload,
            metadata={
                **self.metadata(),
                "duration_ms": (time.perf_counter() - started) * 1000,
            },
        )


class HeuristicDocumentClassifierResource(LocalModelResource):
    resource_id = "heuristic-document-classifier"
    resource_type = "document_classifier"
    version = "1.0.0"
    config_key = "heuristic_document_classifier"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "document_classifier"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        return ResourceResponse(
            status="completed",
            payload=_classify_keywords(str(request.options.get("text", ""))),
            metadata={**self.metadata(), "fallback": "keyword"},
        )


class DocLayoutYOLOResource(LocalModelResource):
    resource_id = "doclayout-yolo"
    resource_type = "layout"
    version = "0.0.4"
    config_key = "doclayout_yolo"

    def health_check(self) -> ResourceHealth:
        return self._health(
            "doclayout_yolo",
            (
                str(
                    self._config().get(
                        "model_file", "doclayout_yolo_docstructbench_imgsz1024.pt"
                    )
                ),
            ),
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "layout"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable", warnings=[health.status], metadata=health.details
            )
        # Page rendering is intentionally owned by the parser/OCR side.  When
        # images are supplied by a host integration, this resource is ready to
        # run local DocLayout-YOLO; native parser block types remain untouched.
        images = request.options.get("page_images", [])
        if not images:
            return ResourceResponse(
                status="completed",
                payload={
                    "pages": {},
                    "method": "doclayout-yolo",
                    "skipped": "no_page_images",
                },
                metadata=self.metadata(),
            )
        try:
            from doclayout_yolo import YOLOv10

            model = YOLOv10(
                str(
                    self._cache_dir()
                    / self._config().get(
                        "model_file", "doclayout_yolo_docstructbench_imgsz1024.pt"
                    )
                )
            )
            result = model.predict(
                images,
                imgsz=int(self._config().get("image_size", 1024)),
                conf=float(self._config().get("confidence", 0.2)),
            )
            return ResourceResponse(
                status="completed",
                payload={
                    "pages": {
                        str(index + 1): str(item) for index, item in enumerate(result)
                    },
                    "method": "doclayout-yolo",
                },
                metadata=self.metadata(),
            )
        except Exception as exc:
            return ResourceResponse(
                status="partial",
                payload={},
                warnings=[f"DocLayout-YOLO fallback: {exc}"],
                metadata=self.metadata(),
            )


class TableTransformerResource(LocalModelResource):
    resource_id = "table-transformer"
    resource_type = "table_recognition"
    version = "1.1"
    config_key = "table_transformer"

    def health_check(self) -> ResourceHealth:
        return self._health(
            "transformers",
            ("config.json", "model.safetensors", "preprocessor_config.json"),
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "table_recognition"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable", warnings=[health.status], metadata=health.details
            )
        tables = {
            getattr(block, "block_id", ""): f"TBL-{getattr(block, 'block_id', '')}"
            for block in request.options.get("blocks", [])
            if getattr(block, "block_type", None) == BlockType.TABLE
        }
        images = list(request.options.get("table_images", []))
        if not images:
            # DOCX/PDF native table blocks are already structured by the parser.
            return ResourceResponse(
                status="completed",
                payload={
                    "tables": tables,
                    "method": "table-transformer",
                    "skipped": "no_table_images",
                },
                metadata=self.metadata(),
            )
        try:
            import torch
            from PIL import Image
            from transformers import (
                AutoImageProcessor,
                TableTransformerForObjectDetection,
            )

            processor = AutoImageProcessor.from_pretrained(
                str(self._cache_dir()), local_files_only=True
            )
            model = TableTransformerForObjectDetection.from_pretrained(
                str(self._cache_dir()), local_files_only=True
            )
            model.eval()
            pages: dict[str, list[dict[str, Any]]] = {}
            for index, image_path in enumerate(images, start=1):
                image = Image.open(image_path).convert("RGB")
                inputs = processor(images=image, return_tensors="pt")
                with torch.no_grad():
                    outputs = model(**inputs)
                target_sizes = torch.tensor([[image.height, image.width]])
                predictions = processor.post_process_object_detection(
                    outputs,
                    threshold=float(self._config().get("confidence", 0.7)),
                    target_sizes=target_sizes,
                )[0]
                pages[str(index)] = [
                    {
                        "label": int(label),
                        "score": round(float(score), 4),
                        "bbox": [round(float(value), 2) for value in box.tolist()],
                    }
                    for label, score, box in zip(
                        predictions["labels"],
                        predictions["scores"],
                        predictions["boxes"],
                    )
                ]
            return ResourceResponse(
                status="completed",
                payload={
                    "tables": tables,
                    "pages": pages,
                    "method": "table-transformer",
                },
                metadata=self.metadata(),
            )
        except Exception as exc:
            return ResourceResponse(
                status="partial",
                payload={"tables": tables},
                warnings=[f"Table Transformer fallback: {exc}"],
                metadata=self.metadata(),
            )


class HeuristicTableResource(LocalModelResource):
    resource_id = "heuristic-table"
    resource_type = "table_recognition"
    version = "1.0.0"
    config_key = "heuristic_table"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "table_recognition"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        tables = {
            getattr(block, "block_id", ""): f"TBL-{getattr(block, 'block_id', '')}"
            for block in request.options.get("blocks", [])
            if getattr(block, "block_type", None) == BlockType.TABLE
        }
        return ResourceResponse(
            status="completed",
            payload={"tables": tables, "method": "native_table_block"},
            metadata={**self.metadata(), "fallback": "native_table_block"},
        )


class TreeSitterCodeResource(LocalModelResource):
    resource_id = "tree-sitter-code"
    resource_type = "code_detection"
    version = "1.0.0"
    config_key = "tree_sitter"

    def health_check(self) -> ResourceHealth:
        if not self._enabled():
            return ResourceHealth(
                available=False, status="disabled", details=self.metadata()
            )
        try:
            import tree_sitter  # noqa: F401
            import tree_sitter_python  # noqa: F401
        except ImportError:
            return ResourceHealth(
                available=False, status="package_missing", details=self.metadata()
            )
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "code_detection"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        values: dict[str, dict[str, Any]] = {}
        for block in request.options.get("blocks", []):
            text = getattr(block, "text", "")
            language = _detect_code_language(text)
            if language:
                _tree_sitter_parse(text, language)
                values[getattr(block, "block_id", "")] = {
                    "is_code": True,
                    "code_language": language,
                }
        return ResourceResponse(
            status="completed", payload={"blocks": values}, metadata=self.metadata()
        )


class HeuristicCodeResource(LocalModelResource):
    resource_id = "heuristic-code"
    resource_type = "code_detection"
    version = "1.0.0"
    config_key = "heuristic_code"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "code_detection"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        values = {
            getattr(block, "block_id", ""): {
                "is_code": True,
                "code_language": _detect_code_language(getattr(block, "text", "")),
            }
            for block in request.options.get("blocks", [])
            if _detect_code_language(getattr(block, "text", ""))
        }
        return ResourceResponse(
            status="completed",
            payload={"blocks": values},
            metadata={**self.metadata(), "fallback": "pattern"},
        )


class SymSpellResource(LocalModelResource):
    resource_id = "symspell"
    resource_type = "spell_correction"
    version = "6.10.0"
    config_key = "symspell"

    def health_check(self) -> ResourceHealth:
        return self._health("symspellpy")

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "spell_correction"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable", warnings=[health.status], metadata=health.details
            )
        from symspellpy import SymSpell, Verbosity

        spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        for term, frequency in {
            "contract": 100,
            "document": 80,
            "configuration": 70,
            "function": 70,
            "python": 70,
            "java": 70,
            "invoice": 60,
            "amount": 60,
        }.items():
            spell.create_dictionary_entry(term, frequency)
        suggestions: list[dict[str, Any]] = []
        for block in request.options.get("blocks", []):
            for match in re.finditer(r"\b[A-Za-z]{4,}\b", getattr(block, "text", "")):
                word = match.group(0).lower()
                candidate = spell.lookup(word, Verbosity.TOP, max_edit_distance=2)
                if candidate and candidate[0].term != word:
                    suggestions.append(
                        {
                            "block_id": getattr(block, "block_id", ""),
                            "original": match.group(0),
                            "suggestion": candidate[0].term,
                            "start_offset": match.start(),
                            "end_offset": match.end(),
                        }
                    )
        return ResourceResponse(
            status="completed",
            payload={"suggestions": suggestions},
            metadata=self.metadata(),
        )


class NoOpSpellResource(LocalModelResource):
    resource_id = "noop-spell"
    resource_type = "spell_correction"
    version = "1.0.0"
    config_key = "noop_spell"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "spell_correction"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        return ResourceResponse(
            status="completed",
            payload={"suggestions": []},
            metadata={**self.metadata(), "fallback": "noop"},
        )


class GLiNERResource(LocalModelResource):
    resource_id = "gliner-ner"
    resource_type = "ner"
    version = "0.2.28"
    config_key = "gliner"

    def health_check(self) -> ResourceHealth:
        return self._health(
            "gliner",
            ("gliner_config.json", "pytorch_model.bin", "deberta-v3-small/config.json"),
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "ner"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        health = self.health_check()
        if not health.available:
            return ResourceResponse(
                status="unavailable", warnings=[health.status], metadata=health.details
            )
        try:
            from gliner import GLiNER

            model = GLiNER.from_pretrained(
                str(self._cache_dir()), local_files_only=True
            )
            labels = list(
                self._config().get("labels", ["person", "organization", "location"])
            )
            result: dict[str, list[dict[str, Any]]] = {}
            for block in request.options.get("blocks", []):
                entities = model.predict_entities(
                    getattr(block, "text", ""),
                    labels,
                    threshold=float(self._config().get("threshold", 0.5)),
                )
                result[getattr(block, "block_id", "")] = [
                    {
                        "text": item["text"],
                        "label": item["label"],
                        "score": float(item["score"]),
                        "start": int(item["start"]),
                        "end": int(item["end"]),
                    }
                    for item in entities
                ]
            return ResourceResponse(
                status="completed",
                payload={"entities": result},
                metadata=self.metadata(),
            )
        except Exception as exc:
            return ResourceResponse(
                status="partial",
                payload={"entities": {}},
                warnings=[f"GLiNER inference fallback: {exc}"],
                metadata=self.metadata(),
            )


class HeuristicNERResource(LocalModelResource):
    resource_id = "heuristic-ner"
    resource_type = "ner"
    version = "1.0.0"
    config_key = "heuristic_ner"

    def health_check(self) -> ResourceHealth:
        return ResourceHealth(
            available=True, status="available", details=self.metadata()
        )

    def supports(self, request: ResourceRequest) -> bool:
        return request.capability == "ner"

    def execute(self, request: ResourceRequest, context: object) -> ResourceResponse:
        values: dict[str, list[dict[str, Any]]] = {}
        pattern = re.compile(
            r"[\u4e00-\u9fffA-Za-z0-9（）()]{2,}(?:有限公司|集团|公司)"
        )
        for block in request.options.get("blocks", []):
            values[getattr(block, "block_id", "")] = [
                {
                    "text": match.group(0),
                    "label": "organization",
                    "score": 0.65,
                    "start": match.start(),
                    "end": match.end(),
                }
                for match in pattern.finditer(getattr(block, "text", ""))
            ]
        return ResourceResponse(
            status="completed",
            payload={"entities": values},
            metadata={**self.metadata(), "fallback": "organization_pattern"},
        )


def _classify_keywords(text: str) -> dict[str, Any]:
    lowered = text.lower()
    rules = (
        ("contract", ("合同", "contract", "甲方", "乙方")),
        ("invoice", ("发票", "invoice")),
        ("code_specification", ("python", "java", "代码", "规范", "class ", "def ")),
    )
    for label, terms in rules:
        if any(term in lowered for term in terms):
            return {"label": label, "confidence": 0.7, "method": "keyword"}
    return {"label": "general_document", "confidence": 0.5, "method": "keyword"}


def _language_code(value: str) -> str:
    return {"zh": "zh-CN", "en": "en", "ja": "ja", "ko": "ko"}.get(value, value)


def _script_language(text: str) -> dict[str, Any]:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return {"language": "zh-CN" if cjk >= latin else "en", "confidence": 0.65}


def _detect_code_language(text: str) -> str | None:
    if "```" in text:
        fenced = re.search(r"```([A-Za-z0-9_+-]+)?", text)
        return (fenced.group(1) if fenced and fenced.group(1) else "text").lower()
    if re.search(r"^\s*(def |class |import |from .* import )", text, re.MULTILINE):
        return "python"
    if re.search(
        r"^\s*(public |private |class |package |import )", text, re.MULTILINE
    ) and (";" in text or "{" in text):
        return "java"
    if "{" in text and (":" in text or "=" in text) and "\n" in text:
        return "config"
    return None


def _tree_sitter_parse(text: str, language: str) -> None:
    """Validate a detected source fragment through Tree-sitter when supported."""
    if language not in {"python", "java", "javascript"}:
        return
    try:
        from tree_sitter import Language, Parser

        if language == "python":
            import tree_sitter_python as grammar
        elif language == "java":
            import tree_sitter_java as grammar
        else:
            import tree_sitter_javascript as grammar
        parser = Parser(Language(grammar.language()))
        parser.parse(text.encode("utf-8"))
    except Exception:
        # Pattern detection remains usable if an optional grammar wheel differs.
        return
