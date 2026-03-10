from workspace.workspace_manager import workspace_manager

class SelfModifyTool:
    def propose_change(self, project: str, relative_path: str, new_content: str):
        return {
            "project": project,
            "relative_path": relative_path,
            "preview": new_content[:200],
            "status": "proposal_ready",
        }

    def apply_change(self, project: str, relative_path: str, new_content: str):
        return workspace_manager.write_file(project, relative_path, new_content, agent_id="self_modify")

self_modify_tool = SelfModifyTool()
