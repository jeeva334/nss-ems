import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, correlation_id_var

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("app")
access_log = logging.getLogger("access")

MAX_BODY_BYTES = 64 * 1024
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_VALID_CID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_DOC_PATHS = ("/docs", "/openapi.json")

app = FastAPI(title="Manpower Portal API", version="0.5.0",
              docs_url=None if settings.app_env == "production" else "/docs", redoc_url=None,
              openapi_url=None if settings.app_env == "production" else "/openapi.json")

app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"], expose_headers=["X-Request-ID"],
)


def _body(code: str, message: str, details=None, cid: str | None = None) -> dict:
    err = {"code": code, "message": message}
    if details:
        err["details"] = details
    if cid:
        err["correlation_id"] = cid  # only on server-side failures, so support can find the log line
    return {"error": err}


def _cid(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def _precheck(request: Request) -> JSONResponse | None:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content=_body("payload_too_large", "Request body is too large."))
    origin = request.headers.get("origin")
    # Cookie-authenticated, state-changing requests must come from an allowed frontend origin.
    if request.method in UNSAFE_METHODS and origin and origin not in settings.cors_origin_list:
        return JSONResponse(status_code=403, content=_body("origin_not_allowed", "Request origin is not allowed."))
    return None


def _security_headers(request: Request, response) -> None:
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    h["Cache-Control"] = "no-store"
    if not request.url.path.startswith(_DOC_PATHS):
        h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.app_env == "production":
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"


@app.middleware("http")
async def hardening(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    cid = incoming if _VALID_CID.match(incoming) else uuid.uuid4().hex  # never trust/echo arbitrary header text into logs
    request.state.correlation_id = cid
    token = correlation_id_var.set(cid)
    start = time.perf_counter()
    try:
        response = _precheck(request) or await call_next(request)
        response.headers["X-Request-ID"] = cid
        _security_headers(request, response)
        # Path only: query strings are never logged.
        access_log.info("request", extra={"http": {"method": request.method, "path": request.url.path,
                                                    "status": response.status_code,
                                                    "duration_ms": round((time.perf_counter() - start) * 1000, 1)}})
        return response
    finally:
        correlation_id_var.reset(token)


@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details))


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content=_body("http_error", str(exc.detail)))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Only location + message are returned: the submitted values (e.g. passwords) are never echoed back.
    fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content=_body("validation_error", "Invalid input.", {"fields": fields}))


def _server_error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    """5xx responses are produced outside the middleware stack, so add its headers here."""
    cid = _cid(request)
    resp = JSONResponse(status_code=status, content=_body(code, message, cid=cid))
    if cid:
        resp.headers["X-Request-ID"] = cid
    _security_headers(request, resp)
    return resp


def _unavailable(request: Request, why: str) -> JSONResponse:
    correlation_id_var.set(_cid(request) or "-")
    log.error("service unavailable: %s", why)  # no stack trace: DB errors can embed connection details
    return _server_error(request, 503, "service_unavailable", "The service is temporarily unavailable. Please try again shortly.")


@app.exception_handler(DBAPIError)
async def db_error(request: Request, exc: DBAPIError):
    code = getattr(exc.orig, "sqlstate", None) or ""
    if code.startswith("23") or code in {"40P01", "40001"}:
        return JSONResponse(status_code=409, content=_body("conflict", "This change conflicts with the current state. Reload and try again."))
    if isinstance(exc, OperationalError) or code.startswith(("08", "53", "57")):
        return _unavailable(request, f"database sqlstate={code or 'none'}")
    correlation_id_var.set(_cid(request) or "-")
    log.exception("database error")
    return _server_error(request, 500, "internal_error", "Internal server error")


@app.exception_handler(PoolTimeout)
async def pool_timeout(request: Request, exc: PoolTimeout):
    return _unavailable(request, "connection pool exhausted")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    correlation_id_var.set(_cid(request) or "-")
    log.exception("unhandled error")  # details go to logs only
    return _server_error(request, 500, "internal_error", "Internal server error")


app.include_router(api_router, prefix="/api/v1")
