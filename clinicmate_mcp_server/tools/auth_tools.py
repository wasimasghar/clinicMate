# auth_tools.py
# Backend-only MCP tools for app signup and sign in. Passwords are hashed here and never returned.
# Hidden from the chat LLM; they refuse to run for single-user clients like Claude Desktop.

from datetime import date
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from repositories import patient_repository
from repositories.patient_repository import PatientError
from services import session_service
from services.password_service import check_password, hash_password

BACKEND_ONLY_ERROR = {"error": "This tool is only for the ClinicMate backend."}
WRONG_LOGIN_ERROR = {"error": "Wrong phone number or password."}

PHONE = Annotated[str, Field(description="Pakistani mobile number, e.g. 03001234567")]
PASSWORD = Annotated[str, Field(min_length=8, max_length=128)]


def register_auth_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def create_account(
        phone: PHONE,
        username: Annotated[str, Field(pattern=r"^[A-Za-z0-9_]{3,30}$", description="3-30 letters, numbers or _")],
        date_of_birth: date,
        password: PASSWORD,
        bio: Annotated[str | None, Field(max_length=300)] = None,
    ) -> dict:
        """BACKEND ONLY: create a patient account after the backend checked the OTP."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        if date_of_birth >= date.today():
            return {"error": "Date of birth must be in the past."}
        try:
            patient = patient_repository.create_account(phone, username, date_of_birth, bio, hash_password(password))
        except PatientError as error:
            return {"error": str(error)}
        return {"patient": patient}

    @mcp.tool()
    def verify_login(phone: PHONE, password: PASSWORD) -> dict:
        """BACKEND ONLY: check phone + password. Returns the patient, or one general error."""
        if session_service.chat_login_allowed():
            return BACKEND_ONLY_ERROR
        try:
            login = patient_repository.get_login(phone)
        except PatientError:
            return WRONG_LOGIN_ERROR
        if login is None or not check_password(password, login["password_hash"]):
            return WRONG_LOGIN_ERROR
        return {"patient": patient_repository.get_patient(login["id"])}