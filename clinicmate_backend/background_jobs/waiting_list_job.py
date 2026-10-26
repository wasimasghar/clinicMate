# waiting_list_job.py
# Builds "a slot opened" notifications for waiting list offers made by the MCP job tool.

from notifications.fcm_sender import Notification


def build_offer_notifications(offers: list[dict]) -> list[Notification]:
    return [
        Notification(
            patient_id=offer["patient_id"],
            title="A slot opened up",
            body=f"{offer['doctor_name']} has a free slot on {offer['time']} at {offer['clinic']}. Open the app to book it.",
            data={"type": "waiting_list_offer", "slot_id": str(offer["slot_id"])},
        )
        for offer in offers
    ]
