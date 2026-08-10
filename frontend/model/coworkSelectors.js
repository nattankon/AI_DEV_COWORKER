export function selectTimeline(state) {
  return state?.events ?? [];
}

export function selectPendingApprovals(state) {
  const events = state?.events ?? [];
  const resolvedIds = new Set(
    events
      .filter((event) => event.type === "approval.resolved")
      .map((event) => event.payload?.approvalId)
      .filter(Boolean),
  );

  return events.filter(
    (event) =>
      event.type === "approval.requested" &&
      event.payload?.approvalId &&
      !resolvedIds.has(event.payload.approvalId),
  );
}

export function selectChangedFiles(state) {
  const files = new Set();
  for (const event of state?.events ?? []) {
    if (event.type !== "diff.proposed") continue;
    for (const file of event.payload?.files ?? []) {
      if (typeof file === "string" && file.trim()) {
        files.add(file.trim());
      }
    }
  }
  return [...files].sort((left, right) => left.localeCompare(right));
}

export function selectTransientStatus(state, sessionId, mode = "") {
  const key = `${sessionId || ""}::${mode || ""}`;
  return state?.transientStatus?.[key] ?? null;
}

export function selectCompletionEvidence(state, sessionId, mode = "") {
  const key = `${sessionId || ""}::${mode || ""}`;
  return state?.completionEvidence?.[key] ?? null;
}
