"""HTTP request and response models.

Separate from the domain documents and from the application command DTOs. A
router that needs a domain type to describe its own payload is a router doing
domain work, and the architecture test forbids it.
"""
