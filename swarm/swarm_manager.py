from concurrent.futures import ThreadPoolExecutor, as_completed

from core.logger import logger
from core.state import state_manager
from swarm.agent_worker import AgentWorker


class SwarmManager:
    def __init__(self):
        self.bees = []

    @property
    def agents(self):
        return self.bees

    def spawn_bees(self, n: int, default_role: str = "coder") -> list:
        from swarm.bee_roles import BEE_ROLES
        start = len(self.bees)
        spawned = []
        for i in range(n):
            role = default_role if default_role in BEE_ROLES else "coder"
            bee = AgentWorker(start + i, role)
            self.bees.append(bee)
            state_manager.active_swarm.append({"id": bee.id, "role": bee.role})
            spawned.append(bee)
        logger.info("%s BEEs spawned with role %s", n, default_role)
        return spawned

    def spawn_agents(self, n: int, default_role: str = "coder"):
        return self.spawn_bees(n, default_role)

    def spawn_specialized_swarm(self, objective: str, n: int = 5) -> list:
        obj_lower = objective.lower()
        roles = []

        if n == 1:
            roles = ["coder"]
        elif n == 2:
            roles = ["planner", "coder"]
        elif n == 3:
            roles = ["planner", "coder", "reviewer"]
        elif n == 4:
            roles = ["planner", "coder", "coder", "reviewer"]
        else:
            roles = ["planner", "architect", "coder", "coder", "reviewer"]
            extra = n - 5
            for i in range(extra):
                roles.append(["tester", "coder", "researcher"][i % 3])

        if any(w in obj_lower for w in ["imagen", "image", "foto", "dibujo", "generar imagen"]):
            roles[0] = "image"
        if any(w in obj_lower for w in ["investigar", "research", "buscar info", "documentación"]):
            if "researcher" not in roles:
                roles.append("researcher")
        if any(w in obj_lower for w in ["escribir", "redactar", "contenido", "copy", "artículo"]):
            if "writer" not in roles:
                roles.append("writer")
        if any(w in obj_lower for w in ["datos", "analizar", "data", "estadísticas"]):
            if "data" not in roles:
                roles.append("data")

        from swarm.bee_roles import BEE_ROLES
        start = len(self.bees)
        spawned = []
        for i, role in enumerate(roles):
            if role not in BEE_ROLES:
                role = "coder"
            bee = AgentWorker(start + i, role)
            self.bees.append(bee)
            state_manager.active_swarm.append({"id": bee.id, "role": bee.role})
            spawned.append(bee)

        logger.info("Swarm de %s BEEs: %s", len(spawned), [b.role for b in spawned])
        return spawned

    def run_swarm_on_objective(self, objective: str, n: int = 5, explicit_roles: list = None) -> dict:
        if explicit_roles:
            from swarm.bee_roles import BEE_ROLES
            start = len(self.bees)
            bees = []
            for i, role in enumerate(explicit_roles[:n]):
                if role not in BEE_ROLES:
                    role = "coder"
                bee = AgentWorker(start + i, role)
                self.bees.append(bee)
                state_manager.active_swarm.append({"id": bee.id, "role": bee.role})
                bees.append(bee)
            logger.info("Swarm con roles explícitos: %s", [b.role for b in bees])
        else:
            bees = self.spawn_specialized_swarm(objective, n)

        tasks = [
            {"step": f"{b.role}: trabajar en objetivo", "objective": objective, "role": b.role}
            for b in bees
        ]

        results = []
        with ThreadPoolExecutor(max_workers=max(len(bees), 1)) as executor:
            futures = {executor.submit(b.run_task, t): b for b, t in zip(bees, tasks)}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.error("BEE error: %s", e)

        return {
            "objective": objective,
            "bees_used": len(bees),
            "roles": [b.role for b in bees],
            "results": results,
        }

    def run_pipeline_on_objective(self, objective: str, roles: list) -> dict:
        """
        BEES encadenadas: el output de cada BEE se pasa como contexto a la siguiente.
        Útil cuando las tareas dependen unas de otras (plan → código → revisión → tests).
        """
        from swarm.bee_roles import BEE_ROLES
        start = len(self.bees)
        bees = []
        for i, role in enumerate(roles):
            if role not in BEE_ROLES:
                role = "coder"
            bee = AgentWorker(start + i, role)
            self.bees.append(bee)
            state_manager.active_swarm.append({"id": bee.id, "role": bee.role})
            bees.append(bee)

        logger.info("Pipeline de %s BEEs: %s", len(bees), [b.role for b in bees])

        results = []
        previous_output = ""
        for bee in bees:
            task = {
                "step": f"{bee.role}: trabajar en objetivo",
                "objective": objective,
                "role": bee.role,
                "context_from_previous_bee": previous_output[:1500] if previous_output else None,
            }
            result = bee.run_task(task)
            previous_output = result.get("result", "")
            results.append(result)
            logger.info("BEE-%s (%s) pipeline output listo", bee.id, bee.role)

        return {
            "objective": objective,
            "mode": "pipeline",
            "bees_used": len(bees),
            "roles": [b.role for b in bees],
            "final_output": previous_output,
            "results": results,
        }

    def ensure_role_count(self, role: str, count: int):
        current = [b for b in self.bees if b.role == role]
        missing = count - len(current)
        if missing > 0:
            self.spawn_bees(missing, default_role=role)

    def assign_task(self, role: str, task):
        for bee in self.bees:
            if bee.role == role:
                return bee.run_task(task)
        if self.bees:
            return self.bees[0].run_task(task)
        return None

    def run_parallel_file_groups(self, role: str, file_groups: list):
        self.ensure_role_count(role, len(file_groups))
        bees = [b for b in self.bees if b.role == role][:len(file_groups)]

        results = []
        with ThreadPoolExecutor(max_workers=max(len(file_groups), 1)) as executor:
            futures = []
            for bee, group in zip(bees, file_groups):
                task = {
                    "step": "write files",
                    "role": role,
                    "files": list(group["files"].keys()),
                    "coder_index": group["coder_index"],
                }
                futures.append(executor.submit(bee.run_task, task))
            for fut in as_completed(futures):
                results.append(fut.result())

        return results

    def list_bees(self):
        return [{"id": b.id, "role": b.role} for b in self.bees]

    def list_agents(self):
        return self.list_bees()

    def reset(self):
        self.bees = []
        state_manager.active_swarm = []


swarm_manager = SwarmManager()
