import html
import logging
from functools import lru_cache
from pathlib import Path
from string import Template

import httpx

from app.core.config import get_settings

log = logging.getLogger("email")
_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "invitation_email.html"


class EmailDeliveryError(Exception):
    """`code` is a sanitized, non-secret reason safe to store and display."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def render_invitation(name: str, link: str, hours: int) -> str:
    return Template(_TEMPLATE.read_text()).substitute(
        name=html.escape(name), link=html.escape(link, quote=True), hours=hours)


class DevOutboxSender:
    """Development only: writes the message to backend/.dev_outbox/. Never logs the link."""
    provider = "dev_outbox"

    def send(self, to: str, subject: str, body_html: str) -> None:
        if get_settings().app_env == "production":
            raise EmailDeliveryError("dev_outbox_disabled_in_production")
        out = Path(__file__).resolve().parents[2] / ".dev_outbox"
        out.mkdir(exist_ok=True)
        (out / f"{to.replace('@', '_at_')}.html").write_text(body_html)
        log.info("invitation written to dev outbox")


class ResendSender:
    provider = "resend"

    def send(self, to: str, subject: str, body_html: str) -> None:
        s = get_settings()
        try:
            r = httpx.post("https://api.resend.com/emails", timeout=10,
                           headers={"Authorization": f"Bearer {s.resend_api_key}"},
                           json={"from": s.email_from, "to": [to], "subject": subject, "html": body_html})
        except httpx.HTTPError:
            raise EmailDeliveryError("provider_unreachable") from None
        if r.status_code >= 300:  # only the status code is kept; the body could echo content
            raise EmailDeliveryError(f"provider_http_{r.status_code}")


@lru_cache
def get_email_sender():
    return ResendSender() if get_settings().email_provider == "resend" else DevOutboxSender()
