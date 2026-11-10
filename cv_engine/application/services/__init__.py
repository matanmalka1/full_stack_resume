"""Synchronous application services, grouped by cohesive lifecycle.

analysis: analysis preparation, activation, and correction.
applications: intake, job text, notes, deletion, and read queries.
drafts: authoring, validation, approval, and history.
knowledge: knowledge queries and fact mutations.
operations: submission, execution, lifecycle, and replacement.

Maintenance, rendering, settings, and shared proposal validation remain standalone
modules.
Import services directly from their owning modules.
"""
