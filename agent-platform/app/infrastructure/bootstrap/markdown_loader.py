from io import BytesIO
from pathlib import Path

import yaml

from app.business.catalog_service import CatalogService
from app.business.knowledge_service import KnowledgeService
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService


class MarkdownCatalogLoader:
    def __init__(
        self,
        catalog_service: CatalogService,
        prompt_service: PromptService,
        tool_service: ToolService,
        knowledge_service: KnowledgeService,
        *,
        skills_dir: str,
        agents_dir: str,
        prompts_dir: str,
        tools_dir: str,
        mcp_servers_dir: str,
        knowledge_dir: str,
    ):
        self._catalog_service = catalog_service
        self._prompt_service = prompt_service
        self._tool_service = tool_service
        self._knowledge_service = knowledge_service
        self._skills_dir = Path(skills_dir)
        self._agents_dir = Path(agents_dir)
        self._prompts_dir = Path(prompts_dir)
        self._tools_dir = Path(tools_dir)
        self._mcp_servers_dir = Path(mcp_servers_dir)
        self._knowledge_dir = Path(knowledge_dir)

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

        agents: dict[str, object] = {}
        agent_metadata: dict[str, dict] = {}
        for file in sorted(self._agents_dir.glob("*.md")):
            metadata, body = self._parse(file)
            agent = await self._catalog_service.create_agent(
                name=metadata["name"],
                description=metadata.get("description", ""),
                instructions=body,
                skill_names=list(metadata.get("skills", [])),
                enabled=bool(metadata.get("enabled", True)),
                source="BOOTSTRAP",
                only_if_missing=True,
            )
            agents[metadata["name"]] = agent
            agent_metadata[metadata["name"]] = metadata

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
                side_effect=str(metadata.get("sideEffect", "READ")),
                approval_policy=str(metadata.get("approvalPolicy", "NEVER")),
                enabled=bool(metadata.get("enabled", True)),
                source="BOOTSTRAP",
                only_if_missing=True,
            )

        await self._load_knowledge()
        await self._assign_agent_knowledge(agents, agent_metadata)

    async def _load_knowledge(self) -> None:
        for file in sorted(self._knowledge_dir.glob("*.md")):
            metadata, body = self._parse(file)
            kb_name = str(metadata.get("knowledgeBase") or "").strip()
            if not kb_name:
                raise ValueError(f"{file} requires 'knowledgeBase' in front matter")

            existing = next(
                (
                    kb
                    for kb in await self._knowledge_service.list_knowledge_bases()
                    if kb.name == kb_name
                ),
                None,
            )
            kb = existing or await self._knowledge_service.create_knowledge_base(
                name=kb_name,
                description=str(metadata.get("knowledgeBaseDescription", "")),
                scope=str(metadata.get("scope", "TENANT")),
                retention_policy=str(metadata.get("retentionPolicy", "PERSISTENT")),
                enabled=bool(metadata.get("enabled", True)),
                chunking_policy=dict(metadata.get("chunkingPolicy", {})),
                metadata={
                    "source": "BOOTSTRAP",
                    "useCase": metadata.get("useCase", "presales"),
                },
            )

            bootstrap_source = file.name
            documents = await self._knowledge_service.list_documents(kb.id)
            if any(
                document.metadata.get("bootstrapSource") == bootstrap_source
                for document in documents
            ):
                continue

            document_name = str(metadata.get("documentName") or file.name)
            await self._knowledge_service.create_uploaded_document(
                kb.id,
                name=document_name,
                stream=BytesIO(body.encode("utf-8")),
                mime_type="text/markdown",
                metadata={
                    "source": "BOOTSTRAP",
                    "bootstrapSource": bootstrap_source,
                    "useCase": metadata.get("useCase", "presales"),
                },
            )

    async def _assign_agent_knowledge(
        self,
        agents: dict[str, object],
        agent_metadata: dict[str, dict],
    ) -> None:
        for name, metadata in agent_metadata.items():
            configured = list(metadata.get("knowledgeBases", []))
            if not configured:
                continue

            agent = agents[name]
            current = await self._knowledge_service.list_agent_knowledge_bases(agent.id)
            merged = {
                item["knowledgeBase"].name: {
                    "name": item["knowledgeBase"].name,
                    "usageMode": item["usageMode"],
                }
                for item in current
            }
            for assignment in configured:
                if isinstance(assignment, str):
                    merged[assignment] = {
                        "name": assignment,
                        "usageMode": "REFERENCE",
                    }
                else:
                    kb_name = assignment["name"]
                    merged[kb_name] = {
                        "name": kb_name,
                        "usageMode": assignment.get("usageMode", "REFERENCE"),
                    }

            await self._knowledge_service.replace_agent_knowledge_bases(
                agent.id,
                list(merged.values()),
            )

    @staticmethod
    def _parse(path: Path) -> tuple[dict, str]:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            raise ValueError(f"{path} must start with YAML front matter")
        _, front_matter, body = content.split("---", 2)
        metadata = yaml.safe_load(front_matter) or {}
        if "name" not in metadata and "knowledgeBase" not in metadata:
            raise ValueError(
                f"{path} requires 'name' or 'knowledgeBase' in front matter"
            )
        return metadata, body.strip()
