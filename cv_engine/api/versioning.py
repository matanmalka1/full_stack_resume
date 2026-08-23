"""The API's own version, and the prefix derived from it.

Separate from `app.py` for one reason: the `202 + Location` helper has to build
an Operation URL, routers import the helper, and `app.py` imports the routers.
Two constants in their own module break that cycle without anything having to
know about it. `app.py` re-exports both, so `cv_engine.api.app.API_PREFIX`
remains the spelling every caller already uses.
"""

from __future__ import annotations

#: The HTTP API version. Deliberately separate from the product version: the
#: product is v2 and the API is v1, and they are free to move apart.
API_VERSION = "1"
API_PREFIX = f"/api/v{API_VERSION}"
