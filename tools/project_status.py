from core.state import state_manager
from swarm.swarm_manager import swarm_manager


class ProjectStatusTool:
    def get_status(self) -> dict:
        return {
            "current_project": state_manager.current_project,
            "queued_tasks": len(state_manager.task_queue),
            "active_agents": swarm_manager.list_agents(),
            "agent_count": len(swarm_manager.agents),
            "memory_keys": list(state_manager.system_memory.keys()),
            "last_uploaded_file": state_manager.last_uploaded_file,
            "authorized_self_modify": state_manager.authorized_self_modify,
        }


project_status_tool = ProjectStatusTool()
