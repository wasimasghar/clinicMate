# account_tools.py
# MCP tools for the patient account: login, register, logout, view and update profile.

from datetime import date
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import patient_repository
from repositories.patient_repository import PatientError
from services import session_service
from services.session_service import NotLoggedInError

PHONE_HINT = "Pakistani mobile number, e.g. 03001234567"
APP_LOGIN_ERROR = {"error": "Login happens in the ClinicMate app, not in chat. Ask the user to log in from the app."}


def register_account_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def login(
        phone: Annotated[str, Field(description=PHONE_HINT)],
    ) -> dict:
        """Log the patient in with their phone number. Needed before booking, cancelling or viewing appointments.
        If the number is not registered, ask for their name and city and call register."""
        if not session_service.chat_login_allowed():
            return APP_LOGIN_ERROR
        try:
            patient = patient_repository.get_patient_by_phone(phone)
        except PatientError as error:
            return {"error": str(error)}

        if patient is None:
            return {"error": "No account with this number.", "next_step": "Ask for full name and city, then call register."}

        session_service.login(patient["id"])
        return {"logged_in": True, "patient": patient}

    @mcp.tool()
    def register(
        full_name: Annotated[str, Field(description="Patient's full name", min_length=2, max_length=100)],
        phone: Annotated[str, Field(description=PHONE_HINT)],
        city: Annotated[str | None, Field(description="City, e.g. 'Lahore'")] = None,
        gender: Annotated[Literal["male", "female", "other"] | None, Field(description="Only if the user shares it")] = None,
        email: Annotated[str | None, Field(description="Optional email")] = None,
    ) -> dict:
        """Create a new patient account and log in. Use only when login said the number is not registered."""
        if not session_service.chat_login_allowed():
            return APP_LOGIN_ERROR
        try:
            patient = patient_repository.create_patient(full_name, phone, city, gender, email)
        except PatientError as error:
            return {"error": str(error)}

        session_service.login(patient["id"])
        return {"registered": True, "logged_in": True, "patient": patient}

    @mcp.tool()
    def logout() -> dict:
        """Log the current patient out."""
        if not session_service.chat_login_allowed():
            return APP_LOGIN_ERROR
        session_service.logout()
        return {"logged_out": True}

    @mcp.tool()
    def get_my_profile() -> dict:
        """Profile of the logged-in patient (name, phone, email, gender, date of birth, city).
        Also tells whether anyone is logged in."""
        try:
            patient_id = session_service.current_patient_id()
        except NotLoggedInError as error:
            return {"logged_in": False, "error": str(error)}
        return {"logged_in": True, "patient": patient_repository.get_patient(patient_id)}

    @mcp.tool()
    def update_my_profile(
        full_name: Annotated[str | None, Field(min_length=2, max_length=100)] = None,
        email: Annotated[str | None, Field(description="New email")] = None,
        city: Annotated[str | None, Field(description="New city, e.g. 'Karachi'")] = None,
        gender: Annotated[Literal["male", "female", "other"] | None, Field()] = None,
        date_of_birth: Annotated[date | None, Field(description="YYYY-MM-DD")] = None,
    ) -> dict:
        """Update the logged-in patient's profile. Send only the fields the user wants to change.
        Phone number cannot be changed here. Confirm the change with the user before calling."""
        try:
            patient_id = session_service.current_patient_id()
            patient = patient_repository.update_patient(
                patient_id,
                city=city,
                full_name=full_name,
                email=email,
                gender=gender,
                date_of_birth=date_of_birth,
            )
        except (NotLoggedInError, PatientError) as error:
            return {"error": str(error)}
        return {"updated": True, "patient": patient}