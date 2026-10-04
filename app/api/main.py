from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hmac
import os

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware

from app.api.runtime import ApiRuntime

from app.api.schemas import (
    ErrorResponse,
    JobSubmissionRequest,
    JobSubmissionResponse,
)


APP_NAME = (
    "Personal GraphRAG Scientific Computing API"
)

APP_VERSION = "0.5.0"

INSECURE_API_KEY_VALUES = frozenset(
    {
        "replace-with-a-long-random-secret",
    }
)


runtime = ApiRuntime.create_default()


def _insecure_local_mode_enabled() -> bool:
    """Return whether the explicit local-development auth bypass is enabled."""

    return os.getenv("GRAPH_RAG_ALLOW_INSECURE_LOCAL", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _configured_api_key() -> str:
    """Return a usable API key, or an empty string for unsafe configuration."""

    api_key = os.getenv("GRAPH_RAG_API_KEY", "").strip()
    if api_key.casefold() in INSECURE_API_KEY_VALUES:
        return ""
    return api_key


def validate_security_configuration() -> None:
    """Fail closed unless an API key or explicit local bypass is configured."""

    if _configured_api_key():
        return
    if _insecure_local_mode_enabled():
        return
    raise RuntimeError(
        "GRAPH_RAG_API_KEY must be set to a non-placeholder secret. Generate "
        "one with `openssl rand -hex 32`. For loopback-only local development, "
        "explicitly set GRAPH_RAG_ALLOW_INSECURE_LOCAL=true."
    )


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    """
    Start the persistent dispatcher when the API starts and
    stop it cleanly when the API shuts down.
    """

    validate_security_configuration()
    app.state.runtime = runtime

    startup_result = runtime.start()

    app.state.startup_result = (
        startup_result
    )

    try:
        yield

    finally:
        runtime.stop()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API for local GraphRAG, named-agent delegation, "
        "persistent scientific jobs, and remote compute workers."
    ),
    lifespan=lifespan,
)


def _allowed_origins() -> list[str]:
    configured = os.getenv(
        "GRAPH_RAG_CORS_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def require_api_key(
    x_api_key: str | None = Header(default=None),
) -> None:
    """Require the configured API key unless local bypass is explicit."""

    expected = _configured_api_key()
    if not expected:
        if _insecure_local_mode_enabled():
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured.",
        )

    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-API-Key header is required.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

# Read-only discovery remains available to in-process clients
# that do not enter the lifespan context.
app.state.runtime = runtime
app.state.startup_result = None


@app.get(
    "/health",
    tags=["system"],
)
def health_check(
    request: Request,
) -> dict:
    """
    Confirm that the API process is running.
    """

    api_runtime = request.app.state.runtime

    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": APP_VERSION,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "dispatcher_running":
            api_runtime.is_running(),
    }


@app.get(
    "/runtime",
    tags=["system"],
)
def runtime_status(
    request: Request,
    _: None = Depends(require_api_key),
) -> dict:
    """
    Return dispatcher, queue, tool, and named-agent status.
    """

    api_runtime = request.app.state.runtime

    return api_runtime.status()


@app.get(
    "/capabilities",
    tags=["discovery"],
)
def list_capabilities(
    request: Request,
    _: None = Depends(require_api_key),
) -> dict:
    """
    Return registered computational domains and tools.
    """

    api_runtime = request.app.state.runtime

    capabilities = (
        api_runtime
        .tool_registry
        .summary()
    )

    return {
        "domain_count":
            len(capabilities),

        "domains":
            capabilities,
    }


@app.get(
    "/agents",
    tags=["discovery"],
)
def list_agents(
    request: Request,
    _: None = Depends(require_api_key),
) -> dict:
    """
    Return registered lightweight named-agent roles.
    """

    api_runtime = request.app.state.runtime

    agents = (
        api_runtime
        .agent_registry
        .describe_agents()
    )

    return {
        "agent_count":
            len(agents),

        "agents":
            agents,
    }


@app.post(
    "/jobs",
    response_model=JobSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
    responses={
        400: {
            "model": ErrorResponse,
        },
        403: {
            "model": ErrorResponse,
        },
        404: {
            "model": ErrorResponse,
        },
        503: {
            "model": ErrorResponse,
        },
    },
)
def submit_job(
    submission: JobSubmissionRequest,
    request: Request,
    _: None = Depends(require_api_key),
) -> JobSubmissionResponse:
    """
    Validate, delegate, durably queue, and asynchronously
    submit one scientific job.
    """

    api_runtime = request.app.state.runtime

    if not api_runtime.is_running():
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Job dispatcher is not running."
            ),
        )

    tool = (
        api_runtime
        .tool_registry
        .get_tool(
            submission.domain,
            submission.tool,
        )
    )

    if tool is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                f"Tool '{submission.tool}' is not "
                f"registered for domain "
                f"'{submission.domain}'."
            ),
        )

    try:
        if submission.agent_id is None:

            result = (
                api_runtime
                .delegation_service
                .delegate(
                    domain=submission.domain,
                    tool=submission.tool,
                    request=submission.request,
                    artifacts=(
                        submission.artifacts
                    ),
                    max_attempts=(
                        submission.max_attempts
                    ),
                )
            )

        else:

            result = (
                api_runtime
                .delegation_service
                .delegate_to(
                    agent_id=(
                        submission.agent_id
                    ),
                    domain=submission.domain,
                    tool=submission.tool,
                    request=submission.request,
                    artifacts=(
                        submission.artifacts
                    ),
                    max_attempts=(
                        submission.max_attempts
                    ),
                )
            )

    except PermissionError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=str(exc),
        ) from exc

    except LookupError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    return JobSubmissionResponse(
        **result
    )


@app.get(
    "/jobs/{job_id}",
    tags=["jobs"],
    responses={
        404: {
            "model": ErrorResponse,
        },
    },
)
def get_job(
    job_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> dict:
    """
    Return the durable SQLite state for one job.
    """

    api_runtime = request.app.state.runtime

    stored = api_runtime.job_store.get(
        job_id
    )

    if stored is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                f"Job not found: {job_id}"
            ),
        )

    return stored
