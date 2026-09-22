from pathlib import Path

import yaml

from app.business.catalog_service import CatalogService
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService


class MarkdownCatalogLoader:
    def __init__(
        self,
        catalog_service: CatalogService,
        prompt_service: PromptService,
        tool_service: ToolService,
        *,
        skills_dir: str,
        agents_dir: str,
        prompts_dir: str,
        tools_dir: str,
        mcp_servers_dir: str,
    ):
        self._catalog_service = catalog_service
        self._prompt_service = prompt_service
        self._tool_service = tool_service
        self._skills_dir = Path(skills_dir)
        self._agents_dir = Path(agents_dir)
        self._prompts_dir = Path(prompts_dir)
        self._tools_dir = Path(tools_dir)
        self._mcp_servers_dir = Path(mcp_servers_dir)

    async def load(self) -> None:
        for file in sorted(self._skills_dir.glob("*.md")):
            metadata, body = self._parse(file)
            await self._catalog_service.create_skill(
                name=metadata["name"],
                description=metadata.get("description", ""),
                instructions=body,
                enabled=bool(metadata.get("enabled", True)),
                source="BOOTSTRAP",
                only_if_missing=True,
            )

        for file in sorted(self._agents_dir.glob("*.md")):
            metadata, body = self._parse(file)
            await self._catalog_service.create_agent(
                name=metadata["name"],
                description=metadata.get("description", ""),
                instructions=body,
                skill_names=list(metadata.get("skills", [])),
                enabled=bool(metadata.get("enabled", True)),
                source="BOOTSTRAP",
                only_if_missing=True,
            )

        for file in sorted(self._prompts_dir.glob("*.md")):
            metadata, body = self._parse(file)
            await self._prompt_service.create_prompt(
                name=metadata["name"],
                description=metadata.get("description", ""),
                content=body,
                version=int(metadata.get("version", 1)),
                enabled=bool(metadata.get("enabled", True)),
                source="BOOTSTRAP",
                only_if_missing=True,
            )

        for file in sorted(self._mcp_servers_dir.glob("*.md")):
            metadata, _ = self._parse(file)
            await self._tool_service.create_mcp_server(
                name=metadata["name"],
                description=metadata.get("description", ""),
                command=metadata["command"],
                args=list(metadata.get("args", [])),
                cwd=metadata.get("cwd"),
                environment=dict(metadata.get("environment", {})),
                enabled=bool(metadata.get("enabled", True)),
                source="BOOTSTRAP",
                only_if_missing=True,
            )

        for file in sorted(self._tools_dir.glob("*.md")):
            metadata, body = self._parse(file)
            await self._tool_service.create_tool(
                name=metadata["name"],
                description=metadata.get("description", ""),
                instructions=body,
                implementation_type=metadata["implementationType"],
                configuration=dict(metadata.get("configuration", {})),
                input_schema=dict(metadata.get("inputSchema", {})),
                enabled=bool(metadata.get("enabled", True)),
                source="BOOTSTRAP",
                only_if_missing=True,
            )

    @staticmethod
    def _parse(path: Path) -> tuple[dict, str]:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            raise ValueError(f"{path} must start with YAML front matter")
        _, front_matter, body = content.split("---", 2)
        metadata = yaml.safe_load(front_matter) or {}
        if "name" not in metadata:
            raise ValueError(f"{path} requires 'name' in front matter")
        return metadata, body.strip()
