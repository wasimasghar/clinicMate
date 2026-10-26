# fcm_sender.py
# Sends push notifications to patients' phones with Firebase Cloud Messaging (FCM).
# Without FIREBASE_CREDENTIALS_FILE in .env it only logs them (development mode).

import asyncio
import logging
from dataclasses import dataclass, field

import firebase_admin
from firebase_admin import credentials, exceptions, messaging

from config.settings import FIREBASE_CREDENTIALS_FILE
from mcp_connection.mcp_client import McpClient

logger = logging.getLogger("fcm_sender")

FCM_BATCH_SIZE = 500  # FCM accepts up to 500 messages per send_each call

_firebase_app: firebase_admin.App | None = None


@dataclass
class Notification:
    patient_id: int
    title: str
    body: str
    data: dict = field(default_factory=dict)  # extra info for the app (values must be strings), e.g. {"type": "reminder"}


def firebase_app() -> firebase_admin.App | None:
    """Firebase connection, created on first use. None when FCM is not configured."""
    global _firebase_app
    if _firebase_app is None and FIREBASE_CREDENTIALS_FILE:
        _firebase_app = firebase_admin.initialize_app(credentials.Certificate(FIREBASE_CREDENTIALS_FILE))
    return _firebase_app


def is_dead_token_error(error: Exception | None) -> bool:
    """The app was uninstalled or the token is broken: delete it instead of retrying."""
    return isinstance(error, (messaging.UnregisteredError, exceptions.InvalidArgumentError))


async def send_notifications(mcp: McpClient, notifications: list[Notification]) -> list[Notification]:
    """Send each notification to all phones of its patient. Returns the notifications that reached at least one phone."""
    if not notifications:
        return []

    app = firebase_app()
    if app is None:
        for notification in notifications:
            logger.info("PUSH (log only, FCM not configured) to patient %s | %s | %s",
                        notification.patient_id, notification.title, notification.body)
        return notifications

    tokens = (await mcp.call_tool("get_device_tokens", {"patient_ids": sorted({n.patient_id for n in notifications})}))["tokens"]
    tokens_by_patient: dict[int, list[str]] = {}
    for row in tokens:
        tokens_by_patient.setdefault(row["patient_id"], []).append(row["token"])

    # One FCM message per (notification, phone)
    messages: list[messaging.Message] = []
    owners: list[tuple[Notification, str]] = []
    for notification in notifications:
        for token in tokens_by_patient.get(notification.patient_id, []):
            messages.append(messaging.Message(
                token=token,
                notification=messaging.Notification(title=notification.title, body=notification.body),
                data={key: str(value) for key, value in notification.data.items()},
            ))
            owners.append((notification, token))

    delivered_ids: set[int] = set()
    dead_tokens: list[str] = []
    for start in range(0, len(messages), FCM_BATCH_SIZE):
        batch = messages[start:start + FCM_BATCH_SIZE]
        # firebase-admin is blocking, so run it in a thread to keep the server responsive
        response = await asyncio.to_thread(messaging.send_each, batch, False, app)
        for offset, result in enumerate(response.responses):
            notification, token = owners[start + offset]
            if result.success:
                delivered_ids.add(id(notification))
            elif is_dead_token_error(result.exception):
                dead_tokens.append(token)
            else:
                logger.warning("FCM failed for patient %s: %s", notification.patient_id, result.exception)

    if dead_tokens:
        await mcp.call_tool("remove_dead_device_tokens", {"tokens": dead_tokens})
        logger.info("removed %s dead device tokens", len(dead_tokens))

    no_phone = [n.patient_id for n in notifications if n.patient_id not in tokens_by_patient]
    if no_phone:
        logger.info("no registered phone for patients %s", sorted(set(no_phone)))
    return [notification for notification in notifications if id(notification) in delivered_ids]
