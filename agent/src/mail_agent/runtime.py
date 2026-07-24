"""Dependency-injection composition root."""

from __future__ import annotations

from dataclasses import dataclass

from .clients.llm import LLMClient
from .clients.ocr import OCRClient
from .clients.results_api import ResultsAPIClient
from .config import AgentSettings
from .graph.builder import MessageGraph
from .integrations.mail import YandexMailAdapter
from .storage.processing_repository import ProcessingRepository
from .summarization.service import AnalysisService
from .worker import PollingWorker


@dataclass
class Runtime:
    worker: PollingWorker
    llm: LLMClient
    ocr: OCRClient
    results_api: ResultsAPIClient
    graph: MessageGraph

    def close(self) -> None:
        self.graph.close()
        self.llm.close()
        self.ocr.close()
        self.results_api.close()


def build_runtime(settings: AgentSettings) -> Runtime:
    settings.prepare_directories()
    mail = YandexMailAdapter(settings.mail_env_file)
    llm, ocr = LLMClient(settings.llm), OCRClient(settings.ocr)
    results_api = ResultsAPIClient(settings.results_api)
    repository = ProcessingRepository(settings.db_path, settings.retries)
    analysis = AnalysisService(settings, llm, ocr)
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        results_api=results_api,
        checkpoint_db=settings.checkpoint_db_path,
        pipeline_version=settings.pipeline_version,
        mark_read_after_success=settings.mail.mark_read_after_success,
    )
    worker = PollingWorker(
        mail=mail,
        graph=graph,
        repository=repository,
        work_dir=settings.work_dir,
        mailbox=settings.mail.mailbox,
        batch_size=settings.mail.batch_size,
        poll_interval_seconds=settings.mail.poll_interval_seconds,
        max_concurrent_messages=settings.mail.max_concurrent_messages,
        unread_only=settings.mail.unread_only,
    )
    return Runtime(worker, llm, ocr, results_api, graph)
