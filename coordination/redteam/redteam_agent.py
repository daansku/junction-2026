"""Harbor agent for reward-integrity testing: runs attack.py inside the agent container (same seat as a real agent)."""
import os
from pathlib import Path
from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

HERE = Path(__file__).parent


class RedTeamAgent(BaseAgent):
    capabilities = AgentCapabilities(mcp_servers=True)

    @staticmethod
    def name() -> str:
        return "redteam"

    def version(self) -> str:
        return "1"

    async def setup(self, environment: BaseEnvironment) -> None:
        await environment.upload_file(HERE / "attack.py", "/tmp/attack.py")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        mode = os.environ.get("ATTACK", "recon")
        r = await environment.exec(f"ATTACK={mode} python3 /tmp/attack.py 2>&1", timeout_sec=1800)
        out = getattr(r, "stdout", None) or str(r)
        dest = Path(os.environ.get("REDTEAM_OUT", str(HERE / f"out-{mode}.txt")))
        dest.write_text(out)
