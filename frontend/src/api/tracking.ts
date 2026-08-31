import { type ApiPath, apiRequest } from "./client";
import type {
  ApplicationMutation,
  CorrectStatusRequest,
  ExternalSubmissionRequest,
  NextActionRequest,
  Submission,
  SubmitApplicationRequest,
  TransitionStatusRequest,
} from "./contracts";

const applicationTrackingPath = (applicationId: string, suffix: string): ApiPath =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/${suffix}` as ApiPath;

export const transitionRecruitmentStatus = async (
  applicationId: string,
  body: TransitionStatusRequest,
): Promise<ApplicationMutation> =>
  (
    await apiRequest<ApplicationMutation>(applicationTrackingPath(applicationId, "status"), {
      method: "POST",
      body,
    })
  ).data;

export const correctRecruitmentStatus = async (
  applicationId: string,
  body: CorrectStatusRequest,
): Promise<ApplicationMutation> =>
  (
    await apiRequest<ApplicationMutation>(
      applicationTrackingPath(applicationId, "status-corrections"),
      { method: "POST", body },
    )
  ).data;

export const recordExternalSubmission = async (
  applicationId: string,
  body: ExternalSubmissionRequest,
): Promise<Submission> =>
  (
    await apiRequest<Submission>(
      applicationTrackingPath(applicationId, "external-submissions"),
      { method: "POST", body },
    )
  ).data;

export const recordInternalSubmission = async (
  applicationId: string,
  body: SubmitApplicationRequest,
): Promise<Submission> =>
  (
    await apiRequest<Submission>(applicationTrackingPath(applicationId, "submissions"), {
      method: "POST",
      body,
    })
  ).data;

export const setNextAction = async (
  applicationId: string,
  body: NextActionRequest,
): Promise<ApplicationMutation> =>
  (
    await apiRequest<ApplicationMutation>(applicationTrackingPath(applicationId, "next-action"), {
      method: "PATCH",
      body,
    })
  ).data;
