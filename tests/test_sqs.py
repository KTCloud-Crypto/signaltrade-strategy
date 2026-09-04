import json
from datetime import datetime, timezone
from uuid import uuid4

from signaltrade_strategy.config import settings
from signaltrade_strategy.sqs import SqsQueueAdapter


def test_invalid_message_does_not_block_valid_message():
    valid_body = json.dumps({"message_id": str(uuid4()), "message_type": "AllocationChanged",
        "occurred_at": datetime.now(timezone.utc).isoformat(), "correlation_id": "c",
        "producer": "trading", "payload": {}})
    class Client:
        def get_queue_url(self, **kwargs): return {"QueueUrl": "queue-url"}
        def receive_message(self, **kwargs):
            return {"Messages": [
                {"MessageId": "bad", "ReceiptHandle": "bad-receipt", "Body": "not-json"},
                {"MessageId": "good", "ReceiptHandle": "good-receipt", "Body": valid_body,
                 "Attributes": {"ApproximateReceiveCount": "2"}},
            ]}
    messages = SqsQueueAdapter(Client(), "strategy").receive(max_messages=10)
    assert len(messages) == 1
    assert messages[0].receipt_handle == "good-receipt"
    assert messages[0].receive_count == 2


def test_aws_client_uses_pod_identity_without_static_keys(monkeypatch):
    captured = {}
    monkeypatch.setattr(settings, "sqs_endpoint_url", None)
    monkeypatch.setattr(settings, "aws_access_key_id", None)
    monkeypatch.setattr(settings, "aws_secret_access_key", None)
    monkeypatch.setattr("signaltrade_strategy.sqs.boto3.client",
                        lambda service, **options: captured.update(options) or object())

    SqsQueueAdapter.from_settings("strategy")

    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured
