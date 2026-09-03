import { queryOptions } from "@tanstack/react-query";

import { type ApiPath, apiRequest } from "./client";
import type { ArtifactVersionDetail, ArtifactVersions } from "./contracts";

/* §20: the artifact surface is addressed by artifact-version ID and by nothing else.
   No endpoint here takes a path, so this module builds none - `artifactDownloadHref` is
   an ID in a URL, exactly like the two reads above it. */
const artifactPath = (artifactVersionId: string): ApiPath =>
  `/api/v1/artifacts/${encodeURIComponent(artifactVersionId)}`;

const applicationArtifactsQueryKey = (applicationId: string) => ["artifacts", applicationId] as const;
const artifactVersionQueryKey = (artifactVersionId: string) => ["artifact", artifactVersionId] as const;

/* Every artifact registered for one Application, newest first is the server's order
   question rather than this client's - the rows arrive as registered and are ordered
   here only for reading, never filtered into a different answer than the one asked for. */
export const applicationArtifactsQueryOptions = (applicationId: string) =>
  queryOptions({
    queryKey: applicationArtifactsQueryKey(applicationId),
    queryFn: async ({ signal }) =>
      (
        await apiRequest<ArtifactVersions>(
          `/api/v1/applications/${encodeURIComponent(applicationId)}/artifacts` as ApiPath,
          { signal },
        )
      ).data,
  });

/* The integrity answer, and the only place it can come from.

   `downloadable`, `size`, and `unavailable_reason` are absent from the list on purpose:
   answering them means running the containment, presence, and hash verification the
   download itself runs, per artifact. So the list stays a cheap read and this one is
   made per row, when the reader opens it - which is also when the answer is worth having,
   because a verification is true of the moment it ran rather than of the moment the
   screen loaded. */
export const artifactVersionQueryOptions = (artifactVersionId: string) =>
  queryOptions({
    queryKey: artifactVersionQueryKey(artifactVersionId),
    queryFn: async ({ signal }) =>
      (await apiRequest<ArtifactVersionDetail>(artifactPath(artifactVersionId), { signal })).data,
  });

/* The technical download: the registered bytes, under the safe delivery filename the
   server names. It verifies containment and hash before it sends anything, and refuses
   with `412` when the payload moved or changed.

   It is not the delivery path for a CV. That stays `recruiter-pdf` on the revision
   screen, which is addressed to the approved revision the reader is looking at. */
export const artifactDownloadHref = (artifactVersionId: string): string =>
  `${artifactPath(artifactVersionId)}/download`;
