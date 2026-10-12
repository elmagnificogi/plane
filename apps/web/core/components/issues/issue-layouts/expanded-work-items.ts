const expandedWorkItemIds = new Set<string>();

export function isWorkItemExpanded(issueId: string) {
  return expandedWorkItemIds.has(issueId);
}

export function setWorkItemExpanded(issueId: string, expanded: boolean) {
  if (expanded) expandedWorkItemIds.add(issueId);
  else expandedWorkItemIds.delete(issueId);
}
