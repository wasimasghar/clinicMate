# device_schemas.py
# Body of POST /devices and DELETE /devices (the app's FCM token).

from typing import Literal

from pydantic import BaseModel, Field


class DeviceTokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=4096, description="FCM registration token from the Flutter app")
    platform: Literal["android", "ios"] = "android"
