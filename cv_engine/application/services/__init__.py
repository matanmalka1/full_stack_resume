"""Synchronous application services, grouped by cohesive lifecycle.

analysis: analysis preparation, activation, correction, and selection.
applications: intake, snapshots, notes, and read queries.
drafts: authoring, validation, approval, and history.
knowledge: knowledge queries and fact mutations.
operations: submission, execution, lifecycle, and replacement.
recruitment: recruitment status and submissions.

Maintenance, rendering, and shared proposal validation remain standalone modules.
Import services directly from their owning modules.
"""
