from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from mail_agent.exceptions import PermanentError
from mail_agent.storage.processing_repository import record_id


def test_record_id_is_stable_and_result_commit_recovers(repository) -> None:
    first = record_id("INBOX", "12", "<id>")
    assert first == record_id("INBOX", "12", "<id>")
    repository.ensure("INBOX", "12", "<id>", "1")
    repository.start(first)
    repository.result_committed(first, {"request_id": "test"})
    assert repository.get(first)["status"] == "result_committed"
    repository.completed(first)
    assert repository.get(first)["status"] == "completed"


def test_permanent_error_is_not_scheduled(repository) -> None:
    stable = repository.ensure("INBOX", "13", None, "1")
    repository.start(stable)
    assert repository.error(stable, "parse", PermanentError("bad file")) == "permanent_error"
    assert not repository.may_attempt(stable)


def test_manual_requeue_resets_a_permanent_error(repository) -> None:
    stable = repository.ensure("INBOX", "14", None, "1")
    repository.start(stable)
    repository.error(stable, "parse", PermanentError("bad file"))

    assert repository.requeue_failed(stable, include_permanent=True)
    item = repository.get(stable)
    assert item is not None
    assert item["status"] == "discovered"
    assert item["attempt_count"] == 1
    assert item["error_type"] is None
    assert repository.may_attempt(stable)


def test_manual_reprocess_resets_a_completed_record(repository) -> None:
    stable = repository.ensure("INBOX", "15", "<id>", "1")
    repository.start(stable)
    repository.result_committed(stable, {"request_id": "test"})
    repository.completed(stable)

    assert repository.requeue_completed(stable)
    item = repository.get(stable)
    assert item is not None
    assert item["status"] == "discovered"
    assert item["api_commit_status"] == "pending"
    assert item["checkpoint"] is None
    assert item["completed_at"] is None
    assert repository.may_attempt(stable)


def test_start_clears_previous_manual_review_flag(repository) -> None:
    stable = repository.ensure("INBOX", "16", "<id>", "1")
    repository.start(stable)
    repository.mark_manual_review(stable, "summarize_message", "PermanentError")
    repository.completed(stable)
    assert repository.requeue_completed(stable)

    repository.start(stable)
    item = repository.get(stable)
    assert item is not None
    assert item["requires_manual_review"] == 0
    assert item["manual_review_stage"] is None


def test_node_execution_claim_is_unique_and_keeps_attempt_history(repository) -> None:
    stable = repository.ensure("INBOX", "17", "<id>", "1")
    values = {
        "record": stable,
        "thread_id": stable,
        "node_name": "summarize_message",
        "pipeline_version": "1",
        "execution_key": "key",
        "input_context_hash": "hash",
        "context": {"checkpoint_thread_id": stable, "input_context_hash": "hash"},
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: repository.claim_node_execution(**values), range(2)))

    assert sorted(str(item["decision"]) for item in claims) == ["busy", "execute"]
    execution = repository.get_node_execution(stable, "summarize_message", execution_key="key")
    assert execution is not None
    assert execution["attempt_count"] == 1
    assert execution["status"] == "running"


def test_recover_abandoned_node_execution_allows_a_new_attempt(repository) -> None:
    stable = repository.ensure("INBOX", "18", "<id>", "1")
    repository.start(stable)
    values = {
        "record": stable,
        "thread_id": stable,
        "node_name": "summarize_message",
        "pipeline_version": "1",
        "execution_key": "abandoned",
        "input_context_hash": "hash",
        "context": {"checkpoint_thread_id": stable, "input_context_hash": "hash"},
    }
    assert repository.claim_node_execution(**values)["decision"] == "execute"

    assert repository.recover_abandoned_node_executions() == 1
    execution = repository.get_node_execution(stable, "summarize_message", execution_key="abandoned")
    assert execution is not None
    assert execution["status"] == "retryable_error"
    assert execution["previous_status"] == "running"
    assert execution["error_type"] == "AbandonedNodeExecution"
    assert [item["status"] for item in repository.node_attempt_history("abandoned")] == ["retryable_error"]

    claim = repository.claim_node_execution(**values)
    assert claim["decision"] == "execute"
    assert claim["execution"]["attempt_count"] == 2


def test_recover_abandoned_checkpointed_node_can_be_finalized(repository) -> None:
    stable = repository.ensure("INBOX", "19", "<id>", "1")
    values = {
        "record": stable,
        "thread_id": stable,
        "node_name": "summarize_message",
        "pipeline_version": "1",
        "execution_key": "checkpointed",
        "input_context_hash": "hash",
        "context": {"checkpoint_thread_id": stable, "input_context_hash": "hash"},
    }
    assert repository.claim_node_execution(**values)["decision"] == "execute"
    repository.store_node_result("checkpointed", {"status": "processing"})

    assert repository.recover_abandoned_node_executions() == 1
    repository.complete_node_execution("checkpointed")

    execution = repository.get_node_execution(stable, "summarize_message", execution_key="checkpointed")
    assert execution is not None
    assert execution["status"] == "completed"
    assert execution["error_type"] is None
    assert [item["status"] for item in repository.node_attempt_history("checkpointed")] == ["completed"]
