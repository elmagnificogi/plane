/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// hooks
import { useProjectState } from "@/hooks/store/use-project-state";
import { projectWorkflowService } from "@/services/project";
import type { TIssueWorkflowTransitions } from "@/services/project";
// local imports
import type { TWorkItemStateDropdownBaseProps } from "./base";
import { WorkItemStateDropdownBase } from "./base";

type TWorkItemStateDropdownProps = Omit<
  TWorkItemStateDropdownBaseProps,
  "stateIds" | "getStateById" | "onDropdownOpen" | "isInitializing"
> & {
  issueId?: string;
  stateIds?: string[];
};

export const StateDropdown = observer(function StateDropdown(props: TWorkItemStateDropdownProps) {
  const { issueId, isForWorkItemCreation = false, projectId, stateIds: propsStateIds, value } = props;
  // router params
  const { workspaceSlug } = useParams();
  // states
  const [stateLoader, setStateLoader] = useState(false);
  const [workflowStateIds, setWorkflowStateIds] = useState<string[] | null>(null);
  const loadedWorkflowKeyRef = useRef<string | null>(null);
  const workflowRequestRef = useRef<{
    key: string;
    promise: Promise<TIssueWorkflowTransitions>;
  } | null>(null);
  // store hooks
  const { fetchProjectStates, getProjectStateIds, getStateById } = useProjectState();
  // derived values
  const stateIds = propsStateIds ?? getProjectStateIds(projectId);
  const visibleStateIds = workflowStateIds ?? stateIds;
  const workspaceSlugString = workspaceSlug?.toString();
  const workflowKey =
    workspaceSlugString && projectId && issueId && !isForWorkItemCreation
      ? `${workspaceSlugString}:${projectId}:${issueId}:${value ?? ""}`
      : null;
  const currentWorkflowKeyRef = useRef(workflowKey);
  currentWorkflowKeyRef.current = workflowKey;

  useEffect(() => {
    setWorkflowStateIds(null);
    setStateLoader(false);
    loadedWorkflowKeyRef.current = null;
  }, [workflowKey]);

  const loadWorkflowTransitions = useCallback(async () => {
    if (!workflowKey || !workspaceSlugString || !projectId || !issueId || isForWorkItemCreation) return;
    if (loadedWorkflowKeyRef.current === workflowKey) return;

    let request = workflowRequestRef.current?.key === workflowKey ? workflowRequestRef.current.promise : undefined;
    if (!request) {
      request = projectWorkflowService.getAvailableTransitions(workspaceSlugString, projectId, issueId);
      workflowRequestRef.current = { key: workflowKey, promise: request };
    }

    try {
      const workflowTransitions = await request;
      if (currentWorkflowKeyRef.current !== workflowKey) return;
      setWorkflowStateIds(
        workflowTransitions.is_enabled
          ? Array.from(
              new Set([
                ...(value ? [value] : []),
                ...workflowTransitions.transitions.map((transition) => transition.state_id),
              ])
            )
          : null
      );
      loadedWorkflowKeyRef.current = workflowKey;
    } catch {
      if (currentWorkflowKeyRef.current === workflowKey) setWorkflowStateIds(value ? [value] : []);
    } finally {
      if (workflowRequestRef.current?.key === workflowKey) workflowRequestRef.current = null;
    }
  }, [isForWorkItemCreation, issueId, projectId, value, workflowKey, workspaceSlugString]);

  // fetch states if not provided
  const onDropdownOpen = async () => {
    if (!workspaceSlugString || !projectId) return;

    const shouldFetchStates = stateIds === undefined || stateIds.length === 0;
    const shouldFilterWorkflowStates = !!issueId && !isForWorkItemCreation;
    const shouldLoadWorkflow = shouldFilterWorkflowStates && loadedWorkflowKeyRef.current !== workflowKey;
    if (!shouldFetchStates && !shouldLoadWorkflow) return;

    setStateLoader(true);
    if (shouldLoadWorkflow) setWorkflowStateIds(value ? [value] : []);

    try {
      await Promise.all([
        shouldFetchStates ? fetchProjectStates(workspaceSlugString, projectId) : Promise.resolve(),
        shouldLoadWorkflow ? loadWorkflowTransitions() : Promise.resolve(),
      ]);
    } finally {
      if (currentWorkflowKeyRef.current === workflowKey) setStateLoader(false);
    }
  };

  const onDropdownPrefetch = () => {
    void loadWorkflowTransitions();
  };

  return (
    <WorkItemStateDropdownBase
      {...props}
      getStateById={getStateById}
      isInitializing={stateLoader}
      stateIds={visibleStateIds ?? []}
      onDropdownOpen={onDropdownOpen}
      onDropdownPrefetch={onDropdownPrefetch}
    />
  );
});
