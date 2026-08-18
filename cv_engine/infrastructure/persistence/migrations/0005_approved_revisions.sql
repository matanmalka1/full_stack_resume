-- ApprovedRevision is the immutable owner of one approved resume's structured
-- content and Markdown projection. The referenced SelectionPlan and
-- ValidationRun already freeze the candidate, policy, Knowledge, and validator
-- contexts; these columns copy their exact recorded values so the revision is
-- self-describing without re-reading mutable Knowledge.
CREATE TABLE approved_revisions (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    job_snapshot_id TEXT NOT NULL REFERENCES job_snapshots(id),
    job_analysis_id TEXT NOT NULL REFERENCES job_analyses(id),
    selection_plan_id TEXT NOT NULL REFERENCES selection_plans(id),
    working_draft_id TEXT NOT NULL REFERENCES working_drafts(id),
    draft_edit_version INTEGER NOT NULL CHECK (draft_edit_version > 0),
    draft_content_hash TEXT NOT NULL,
    resume_json_path TEXT NOT NULL UNIQUE,
    resume_json_hash TEXT NOT NULL,
    resume_markdown_path TEXT NOT NULL UNIQUE,
    resume_markdown_hash TEXT NOT NULL,
    candidate_context_version TEXT NOT NULL,
    candidate_context_hash TEXT NOT NULL,
    facts_version TEXT NOT NULL,
    knowledge_context_hash TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    selection_policy_version TEXT NOT NULL,
    track_emphasis_dependencies_json TEXT NOT NULL,
    validation_run_id TEXT NOT NULL UNIQUE REFERENCES validation_runs(id),
    validator_versions_json TEXT NOT NULL,
    decision_provenance_json TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    UNIQUE(application_id, version_number)
);

CREATE TRIGGER no_update_approved_revisions BEFORE UPDATE ON approved_revisions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

CREATE TRIGGER no_delete_approved_revisions BEFORE DELETE ON approved_revisions
BEGIN
    SELECT RAISE(ABORT, 'immutable record');
END;

-- Historical artifact-version rows predate ApprovedRevision and deliberately
-- remain NULL. Migration must not manufacture a revision identity that was
-- never recorded.
ALTER TABLE artifact_versions
ADD COLUMN revision_id TEXT REFERENCES approved_revisions(id);

CREATE INDEX idx_versions_revision ON artifact_versions(revision_id);
