import base64
import hashlib
import logging
import os
import secrets
import threading
import tkinter
import webbrowser
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps

import time

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from config import Config, appversion

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger()

USER_AGENT = f"EDCD-hugh-{appversion()}"


class BearerAuth(httpx.Auth):
    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


def cacheable(ttl: float, name: str):
    def decorator(func):
        cache = {}  # stored as {(self_id, args, kwargs): (value, expire_time)}

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            key = name
            now = time.time()

            if key in cache:
                value, expire_at = cache[key]
                if now < expire_at:
                    return value  # still valid

            # Compute fresh value
            value = func(self, *args, **kwargs)
            cache[key] = (value, now + ttl)
            return value

        return wrapper

    return decorator


class CApi:
    CLIENT_ID: str = (
        os.getenv("HUGH_CLIENT_ID") or "5758c1f5-e107-4b47-ac1f-a4c2b855acdd"
    )
    AUTH_BASE_URL: str = "https://auth.frontierstore.net"
    CAPI_URL: str = "https://companion.orerve.net"

    verifier: str
    state: str
    challenge: str
    master: tkinter.Tk
    storage: dict = {}
    thread: threading.Thread | None = None
    redirect_url: str
    profile_data: dict[str, Any] = {}

    client: httpx.Client

    access_token: str | None = None
    expires: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    refresh_token: str | None = None

    def __init__(self, master: tkinter.Tk, refresh_token: str | None = None):
        self.master = master

        self.refresh_token = refresh_token
        self.httpd = None
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT})
        self.thread: threading.Thread | None = None
        master.bind_all("<<OauthRedirect>>", self.redirect)

    def start(self) -> None:
        """Start the HTTP server thread."""
        self.httpd = HTTPServer(
            ("localhost", 0), self.handler(self.master, self.storage)
        )
        self.redirect_url = f"http://localhost:{self.httpd.server_port}/auth"
        logger.info(f"Web server listening on {self.redirect_url}")
        self.thread = threading.Thread(
            target=self.worker, name="OAuth worker", daemon=True
        )
        self.thread.start()

    def worker(self) -> None:
        self.httpd.handle_request()

    def start_auth(self) -> None:
        if self.thread is None or not self.thread.is_alive():
            self.start()
        webbrowser.open(self.auth_url())

    def redirect(self, event: tkinter.Event) -> None:
        logger.debug(f"Received {self.storage['state']} {self.storage['code']}")
        if self.storage["state"] != self.state:
            logger.error("state mismatch")
            return
        res = self.client.post(
            f"{self.AUTH_BASE_URL}/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            },
            data={
                "redirect_uri": self.redirect_url,
                "code": self.storage["code"],
                "grant_type": "authorization_code",
                "code_verifier": self.verifier,
                "client_id": self.CLIENT_ID,
            },
        )
        if res.status_code == 200:
            data = res.json()
            self.access_token = data["access_token"]
            self.expires = datetime.now(timezone.utc) + timedelta(
                seconds=data["expires_in"]
            )
            self.refresh_token = data["refresh_token"]
            self.profile()
            self.master.event_generate("<<CAPIAuthorized>>", when="tail")

    def refresh_request(self) -> bool:
        res = self.client.post(
            f"{self.AUTH_BASE_URL}/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "client_id": self.CLIENT_ID,
                "refresh_token": self.refresh_token,
            },
        )
        if res.status_code != 200:
            return False
        data = res.json()
        self.access_token = data["access_token"]
        self.expires = datetime.now(timezone.utc) + timedelta(
            seconds=data["expires_in"]
        )
        self.refresh_token = data["refresh_token"]
        self.master.event_generate("<<CAPIRefreshed>>", when="tail")
        return True

    def authorize(self):
        if self.refresh_request():
            self.profile()
            return
        self.start_auth()

    @property
    def cmdr(self) -> str | None:
        if "commander" in self.profile_data:
            return self.profile_data["commander"].get("name")
        return None

    @property
    def id(self) -> str | None:
        if "commander" in self.profile_data:
            return self.profile_data["commander"].get("id")
        return None

    def check_expiry(self) -> bool:
        return self.expires < (datetime.now(timezone.utc) + timedelta(minutes=5))

    @cacheable(120, "profile")
    def profile(self) -> dict[str, Any]:
        if self.check_expiry():
            if not self.refresh_request():
                raise RuntimeError("Reauthentication required")

        res = self.client.get(
            f"{self.CAPI_URL}/profile", auth=BearerAuth(self.access_token)
        )
        data = res.json()
        self.profile_data = data
        return data

    @cacheable(60, "fleet_carrier")
    def fleet_carrier(self) -> dict[str, Any]:
        if self.check_expiry():
            if not self.refresh_request():
                raise RuntimeError("Reauthentication required")

        res = self.client.get(
            f"{self.CAPI_URL}/fleetcarrier", auth=BearerAuth(self.access_token)
        )
        data = res.json()
        return data

    @staticmethod
    def base64_url_encode_nopad(text: bytes) -> str:
        """Base64 encode text for URL."""
        return base64.urlsafe_b64encode(text).decode().replace("=", "")

    @staticmethod
    def base64_url_encode(text: bytes) -> str:
        """Base64 encode text for URL."""
        return base64.urlsafe_b64encode(text).decode().replace("=", "")

    def auth_url(self):
        self.verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .rstrip(b"=")
            .decode("ascii")
        )

        self.challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest())
            .rstrip(b"=")
            .decode("ascii")
        )

        self.state = (
            base64.urlsafe_b64encode(hashlib.sha256(secrets.token_bytes(32)).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        return (
            f"{self.AUTH_BASE_URL}/auth?audience=frontier,steam,epic&scope=auth%20capi&response_type=code"
            + f"&client_id={self.CLIENT_ID}&code_challenge={self.challenge}&"
            + f"code_challenge_method=S256&state={self.state}&redirect_uri={self.redirect_url}"
        )

    def handler(self, master: tkinter.Tk, storage: dict):
        class HTTPRequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                """Handle GET Request."""
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                if parsed.path == "/auth":
                    storage["code"] = params.get("code", [""])[0]
                    storage["state"] = params.get("state", [""])[0]

                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        (
                            "<html>"
                            "<head>"
                            "<title>Authentication successful - Elite: Dangerous</title>"
                            "<style>"
                            'body { background-color: #000; color: #fff; font-family: "Helvetica Neue", Arial, sans-serif; }'
                            "h1 { text-align: center; margin-top: 100px; }"
                            "p { text-align: center; }"
                            "</style>"
                            "</head>"
                            "<body>"
                            "<h1>Authentication successful</h1>"
                            "<p>Thank you for authenticating.</p>"
                            "<p>You may close this browser tab now.</p>"
                            "</body>"
                            "</html>"
                        ).encode()
                    )

                    master.event_generate("<<OauthRedirect>>", when="tail")
                else:
                    self.send_error(404, "Not Found")

            def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
                """Override to prevent logging."""

        return HTTPRequestHandler


class CAPIManager:
    def __init__(self, master: tkinter.Tk, config: Config):
        self.master = master
        self.config = config
        self.callbacks: dict[CApi, Callable] = {}
        self.cmdrs: dict[str, CApi] = {}
        self.fids: dict[str, CApi] = {}
        self.pending_companions = []
        master.bind("<<CAPIRefreshed>>", self.on_refresh)
        master.bind("<<CAPIAuthorized>>", self.on_refresh)

    def save(self):
        logger.info("Saving CAPI tokens")
        saved = self.config.get_dict("tokens", section="hugh.capi") or {}
        for k, v in self.fids.items():
            saved[f"F{k}"] = {"cmdr": v.cmdr, "token": v.refresh_token}
        self.config.set("tokens", saved, section="hugh.capi")
        self.config.save()

    def on_refresh(self, *args):
        for x in self.pending_companions:
            if x.id and x.cmdr:
                self.cmdrs[x.cmdr] = x
                self.fids[x.id] = x
                self.pending_companions.remove(x)
                if self.callbacks[x]:
                    self.callbacks[x](x)
        self.save()

    def login_saved(self, config: Config):
        saved: dict[str, Any] = config.get_dict("tokens", section="hugh.capi")
        if saved is None:
            return
        for k, v in saved.items():
            self.login(v["token"])

    def login(
        self, refresh_token: str | None = None, callback: Callable | None = None
    ) -> None:
        x = CApi(self.master, refresh_token)
        self.pending_companions.append(x)
        self.callbacks[x] = callback
        x.authorize()

    def get_by_cmdr(self, cmdr: str) -> CApi | None:
        return self.cmdrs.get(cmdr)

    def get_by_fid(self, fid: str) -> CApi | None:
        return self.fids.get(fid)


# master = tkinter.Tk()
#
# auth = Companion(config, master)
#
# auth.authorize()
# with open("fc.json", "w") as f:
#     json.dump(auth.fleet_carrier(), f)
# master.mainloop()
