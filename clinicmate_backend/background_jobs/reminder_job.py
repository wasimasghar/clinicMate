# reminder_job.py
# Builds appointment reminder notifications from the due reminders returned by the MCP job tool.

from notifications.fcm_sender import Notification


def build_reminder_notifications(reminders: list[dict]) -> list[Notification]:
    return [
        Notification(
            patient_id=reminder["patient_id"],
            title="Appointment reminder",
            body=(
                f"{reminder['doctor_name']} on {reminder['day']} {reminder['date']} at {reminder['start_time']}, "
                f"{reminder['clinic']}, {reminder['area']}. Reply in the app to cancel or reschedule."
            ),
            data={"type": "reminder", "appointment_id": str(reminder["appointment_id"])},
        )
        for reminder in reminders
    ]
