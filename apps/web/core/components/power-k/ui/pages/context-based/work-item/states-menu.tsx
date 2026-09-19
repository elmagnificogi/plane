/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Command } from "cmdk";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane types
import { useParams } from "next/navigation";
import type { IState, TIssue } from "@plane/types";
import { Spinner } from "@plane/ui";
// hooks
import { useProjectState } from "@/hooks/store/use-project-state";
import { projectWorkflowService } from "@/services/project";
// local imports
import { PowerKProjectStatesMenuItems } from "./state-menu-item";

type Props = {
  handleSelect: (stateId: string) => void;
  workItemDetails: TIssue;
};

export const PowerKProjectStatesMenu = observer(function PowerKProjectStatesMenu(props: Props) {
  const { workItemDetails } = props;
  // router
  const { workspaceSlug } = useParams();
  const workspaceSlugString = workspaceSlug?.toString();
  const issueProjectId = workItemDetails.project_id;
  const issueId = workItemDetails.id;
  // store hooks
  const { getProjectStateIds, getStateById } = useProjectState();
  const { data: workflowTransitions, error: workflowTransitionsError } = useSWR(
    workspaceSlugString && issueProjectId && issueId
      ? `issue-workflow-transitions-${workspaceSlugString}-${issueProjectId}-${issueId}`
      : null,
    () => {
      if (!workspaceSlugString || !issueProjectId || !issueId) throw new Error("Work item context is unavailable");
      return projectWorkflowService.getAvailableTransitions(workspaceSlugString, issueProjectId, issueId);
    }
  );
  // derived values
  const projectStateIds = workItemDetails.project_id ? getProjectStateIds(workItemDetails.project_id) : undefined;
  const projectStates = projectStateIds ? projectStateIds.map((stateId) => getStateById(stateId)) : undefined;
  const workflowStateIds = workflowTransitions?.is_enabled
    ? new Set([workItemDetails.state_id, ...workflowTransitions.transitions.map((transition) => transition.state_id)])
    : workflowTransitionsError
      ? new Set([workItemDetails.state_id])
      : undefined;
  const filteredProjectStates = projectStates
    ? projectStates.filter((state): state is IState => !!state && (!workflowStateIds || workflowStateIds.has(state.id)))
    : undefined;

  if (!filteredProjectStates || (!workflowTransitions && !workflowTransitionsError)) return <Spinner />;

  return (
    <Command.Group>
      <PowerKProjectStatesMenuItems
        {...props}
        projectId={workItemDetails.project_id ?? undefined}
        selectedStateId={workItemDetails.state_id ?? undefined}
        states={filteredProjectStates}
        workspaceSlug={workspaceSlugString}
      />
    </Command.Group>
  );
});
