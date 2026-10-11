from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from cv_engine.infrastructure.rendering import _isolated_route_handler, render_pdf


class _Route:
    def __init__(self) -> None:
        self.action: str | None = None

    def continue_(self) -> None:
        self.action = "continue"

    def abort(self, _reason: str) -> None:
        self.action = "abort"


class _Request:
    def __init__(self, url: str, *, navigation: bool = False) -> None:
        self.url = url
        self._navigation = navigation

    def is_navigation_request(self) -> bool:
        return self._navigation


def test_renderer_route_allows_exactly_the_initial_html_navigation() -> None:
    allowed = "file:///attempt/cv.html"
    handle = _isolated_route_handler(allowed)

    first = _Route()
    handle(first, _Request(allowed, navigation=True))
    assert first.action == "continue"

    for url, navigation in (
        (allowed, True),
        ("file:///another-user/cv.html", True),
        ("https://example.com/tracker", False),
        ("data:text/plain,secret", False),
        ("blob:null/secret", False),
    ):
        route = _Route()
        handle(route, _Request(url, navigation=navigation))
        assert route.action == "abort"


@pytest.mark.browser
def test_renderer_aborts_external_requests_before_they_leave_chromium(tmp_path) -> None:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            requests.append(self.path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, _format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        html = tmp_path / "cv.html"
        html.write_text(
            "<!doctype html><html><body><main data-cv-page>CV"
            f'<img src="http://127.0.0.1:{port}/image">'
            f'<iframe src="http://127.0.0.1:{port}/frame"></iframe>'
            "</main></body></html>",
            encoding="utf-8",
        )
        render_pdf(html, tmp_path / "cv.pdf")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert requests == []
