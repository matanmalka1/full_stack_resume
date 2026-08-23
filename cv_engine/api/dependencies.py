"""How a router reaches the services.

The container is built once, at composition time, and stored on the application
state. Nothing is constructed per request: building a service per request would
mean opening stores and running Knowledge recovery on every call.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from .services import ApiServices

_STATE_KEY = "api_services"


def install_services(app, services: ApiServices) -> None:
    setattr(app.state, _STATE_KEY, services)


def get_services(request: Request) -> ApiServices:
    return getattr(request.app.state, _STATE_KEY)


Services = Annotated[ApiServices, Depends(get_services)]
