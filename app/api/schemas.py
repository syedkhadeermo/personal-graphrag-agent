from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class JobSubmissionRequest(BaseModel):
    """
    Validated API request for asynchronous job submission.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    domain: str = Field(
        min_length=1,
        max_length=100,
    )

    tool: str = Field(
        min_length=1,
        max_length=100,
    )

    request: dict[str, Any] = Field(
        default_factory=dict
    )

    artifacts: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    max_attempts: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )

    agent_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    @field_validator(
        "domain",
        "tool",
        "agent_id",
    )
    @classmethod
    def strip_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        stripped = value.strip()

        if not stripped:
            raise ValueError(
                "Value cannot be empty."
            )

        return stripped


class JobSubmissionResponse(BaseModel):
    """
    Response returned immediately after durable submission.
    """

    job_id: str
    agent_id: str
    domain: str
    tool: str
    status: str


class ErrorResponse(BaseModel):
    """
    Standard API error response.
    """

    detail: str