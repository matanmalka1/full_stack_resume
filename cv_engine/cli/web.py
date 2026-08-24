"""The ``cv web`` supervisor command."""

from __future__ import annotations

import sys

from ..runtime.web import WebRuntime, open_existing, select_web_endpoint, source_frontend_dist
from .context import CommandContext, _command
from .output import _print


@_command("web")
def _web(context: CommandContext) -> int:
    services = context.built_services
    endpoint = select_web_endpoint(services, preferred_port=context.args.port)
    open_browser = not context.args.no_open and services.settings.read().open_browser_on_launch
    if endpoint.reuse_existing:
        _print({"url": endpoint.url, "reused_existing": True})
        open_existing(endpoint, open_browser=open_browser)
        return 0

    frontend_dist = source_frontend_dist()
    runtime = WebRuntime(services, endpoint, frontend_dist, config=context.config)
    _print(
        {
            "url": endpoint.url,
            "reused_existing": False,
            "frontend_dist": str(frontend_dist),
        }
    )
    sys.stdout.flush()
    runtime.run(open_browser=open_browser)
    return 0
