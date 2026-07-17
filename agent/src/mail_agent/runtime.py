"""Dependency-injection composition root."""

from __future__ import annotations

from dataclasses import dataclass

from .clients.llm import LLMClient
from .clients.ocr import OCRClient
from .config import AgentSettings
from .graph.builder import MessageGraph
from .integrations.drive import YandexDriveAdapter
from .integrations.mail import YandexMailAdapter
from .storage.processing_repository import ProcessingRepository
from .storage.workbook import WorkbookRepository
from .summarization.service import AnalysisService
from .worker import PollingWorker


@dataclass
class Runtime:
    worker: PollingWorker
    llm: LLMClient
    ocr: OCRClient
    graph: MessageGraph

    def close(self) -> None:
        self.graph.close()
        self.llm.close()
        self.ocr.close()


def build_runtime(settings: AgentSettings) -> Runtime:
    settings.prepare_directories()
    mail = YandexMailAdapter(settings.mail_env_file)
    drive = YandexDriveAdapter(settings.drive_env_file)
    llm, ocr = LLMClient(settings.llm), OCRClient(settings.ocr)
    repository = ProcessingRepository(settings.db_path, settings.retries)
    analysis = AnalysisService(settings, llm, ocr)
    workbook = WorkbookRepository(drive, settings.table)
    graph = MessageGraph(
        mail=mail,
        repository=repository,
        analysis=analysis,
        workbook=workbook,
        checkpoint_db=settings.checkpoint_db_path,
        pipeline_version=settings.pipeline_version,
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
    )
    return Runtime(worker, llm, ocr, graph)
