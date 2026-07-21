from __future__ import annotations

from datetime import datetime, timezone
import logging
from time import perf_counter
from typing import Protocol

from zyrelay.app.models import ProcessingStepRecord

from .context import ProcessingContext


class PipelineStep(Protocol):
    name: str

    def execute(self, context: ProcessingContext) -> ProcessingContext: ...


class Pipeline:
    def __init__(self, steps: list[PipelineStep]) -> None:
        self.steps = steps

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        logger = logging.getLogger("zyrelay.pipeline")
        for step in self.steps:
            started_at = datetime.now(timezone.utc)
            started = perf_counter()
            try:
                context = step.execute(context)
            except Exception as exc:
                ended_at = datetime.now(timezone.utc)
                error_code = getattr(exc, "error_code", "unexpected_error")
                context.steps.append(
                    ProcessingStepRecord(
                        name=step.name,
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_ms=(perf_counter() - started) * 1000,
                        status="failed",
                        error_code=error_code,
                        error=str(exc),
                    )
                )
                context.errors.append(
                    {"step": step.name, "error_code": error_code, "message": str(exc)}
                )
                logger.error(
                    "pipeline step failed",
                    extra={
                        "request_id": context.request_id,
                        "task_id": context.task_id,
                        "document_id": (
                            context.document.document_id if context.document else None
                        ),
                        "pipeline_step": step.name,
                        "duration_ms": (perf_counter() - started) * 1000,
                        "status": "failed",
                        "error_code": error_code,
                    },
                )
                raise
            ended_at = datetime.now(timezone.utc)
            context.steps.append(
                ProcessingStepRecord(
                    name=step.name,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=(perf_counter() - started) * 1000,
                    status="completed",
                )
            )
            logger.info(
                "pipeline step completed",
                extra={
                    "request_id": context.request_id,
                    "task_id": context.task_id,
                    "document_id": (
                        context.document.document_id if context.document else None
                    ),
                    "pipeline_step": step.name,
                    "duration_ms": (perf_counter() - started) * 1000,
                    "status": "completed",
                },
            )
        return context
