/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { projectWorkflowService } from "@/services/project";

type PromptListener = () => void;
type FailureListener = (names: string[]) => void;

let pendingResolve: ((completeDescendants: boolean) => void) | null = null;
const promptListeners = new Set<PromptListener>();
const failureListeners = new Set<FailureListener>();
const pendingCascadeIssueIds = new Set<string>();

function notifyPromptListeners() {
  promptListeners.forEach((listener) => listener());
}

export function subscribeDescendantCompletionPrompt(listener: PromptListener) {
  promptListeners.add(listener);
  return () => {
    promptListeners.delete(listener);
  };
}

export function isDescendantCompletionPromptOpen() {
  return pendingResolve !== null;
}

export function resolveDescendantCompletionPrompt(completeDescendants: boolean) {
  const resolve = pendingResolve;
  pendingResolve = null;
  notifyPromptListeners();
  resolve?.(completeDescendants);
}

export function subscribeDescendantCompletionFailures(listener: FailureListener) {
  failureListeners.add(listener);
  return () => {
    failureListeners.delete(listener);
  };
}

export function notifyDescendantCompletionFailures(names: string[]) {
  if (names.length === 0) return;
  failureListeners.forEach((listener) => listener(names));
}

export function markDescendantCompletion(issueId: string) {
  pendingCascadeIssueIds.add(issueId);
}

export function consumeDescendantCompletion(issueId: string) {
  const marked = pendingCascadeIssueIds.has(issueId);
  pendingCascadeIssueIds.delete(issueId);
  return marked;
}

export async function confirmDescendantCompletion(args: {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  stateId: string;
}): Promise<boolean> {
  if (pendingResolve) return false;

  try {
    const preview = await projectWorkflowService.previewDescendantCompletion(
      args.workspaceSlug,
      args.projectId,
      args.issueId,
      args.stateId
    );
    if (!preview.should_prompt) return false;
  } catch {
    return false;
  }

  return new Promise((resolve) => {
    pendingResolve = resolve;
    notifyPromptListeners();
  });
}
