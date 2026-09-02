from dataclasses import dataclass
from typing import Any

import boto3

from signaltrade_strategy.config import settings
from signaltrade_strategy.message_contract import MessageEnvelope


@dataclass(frozen=True)
class QueueMessage:
    receipt_handle: str
    envelope: MessageEnvelope
    receive_count: int


class SqsQueueAdapter:
    def __init__(self, client: Any, queue_name: str) -> None:
        self._client = client
        self._queue_name = queue_name
        self._queue_url: str | None = None

    @classmethod
    def from_settings(cls, queue_name: str) -> "SqsQueueAdapter":
        options: dict[str, Any] = {
            "region_name": settings.aws_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.sqs_endpoint_url:
            options["endpoint_url"] = settings.sqs_endpoint_url
        return cls(boto3.client("sqs", **options), queue_name)

    def _get_queue_url(self) -> str:
        if self._queue_url is None:
            self._queue_url = self._client.get_queue_url(QueueName=self._queue_name)["QueueUrl"]
        return self._queue_url

    def receive(self, *, max_messages: int = 1, wait_time_seconds: int = 10,
                visibility_timeout: int = 30) -> list[QueueMessage]:
        response = self._client.receive_message(
            QueueUrl=self._get_queue_url(), MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_time_seconds, VisibilityTimeout=visibility_timeout,
            AttributeNames=["ApproximateReceiveCount"],
        )
        return [QueueMessage(item["ReceiptHandle"], MessageEnvelope.from_json(item["Body"]),
                             int(item.get("Attributes", {}).get("ApproximateReceiveCount", "1")))
                for item in response.get("Messages", [])]

    def acknowledge(self, message: QueueMessage) -> None:
        self._client.delete_message(QueueUrl=self._get_queue_url(), ReceiptHandle=message.receipt_handle)
