from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure.bootstrap.markdown_loader import MarkdownCatalogLoader


class FakeCatalogService:
    def __init__(self):
        self.agents = {}

    async def create_skill(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    async def create_agent(self, **kwargs):
        existing = self.agents.get(kwargs["name"])
        if existing:
            return existing
        agent = SimpleNamespace(id=uuid4(), name=kwargs["name"])
        self.agents[kwargs["name"]] = agent
        return agent


class FakePromptService:
    async def create_prompt(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)


class FakeToolService:
    async def create_mcp_server(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    async def create_tool(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)


class FakeKnowledgeService:
    def __init__(self):
        self.kbs = {}
        self.documents = {}
        self.assignments = {}

    async def list_knowledge_bases(self, enabled_only=False):
        return list(self.kbs.values())

    async def create_knowledge_base(self, **kwargs):
        kb = SimpleNamespace(id=uuid4(), name=kwargs["name"])
        self.kbs[kb.name] = kb
        self.documents[kb.id] = []
        return kb

    async def list_documents(self, kb_id):
        return list(self.documents.get(kb_id, []))

    async def create_uploaded_document(
        self,
        kb_id,
        *,
        name,
        stream,
        mime_type,
        metadata,
    ):
        document = SimpleNamespace(
            id=uuid4(),
            name=name,
            metadata=metadata,
            content=stream.read().decode("utf-8"),
        )
        self.documents[kb_id].append(document)
        return document

    async def list_agent_knowledge_bases(self, agent_id):
        return self.assignments.get(agent_id, [])

    async def replace_agent_knowledge_bases(self, agent_id, assignments):
        result = []
        for assignment in assignments:
            kb = self.kbs[assignment["name"]]
            result.append(
                {
                    "knowledgeBase": kb,
                    "usageMode": assignment.get("usageMode", "REFERENCE"),
                }
            )
        self.assignments[agent_id] = result


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


@pytest.mark.asyncio
async def test_bootstraps_knowledge_idempotently_and_assigns_it_to_agent(tmp_path: Path):
    skills = tmp_path / "skills"
    agents = tmp_path / "agents"
    prompts = tmp_path / "prompts"
    tools = tmp_path / "tools"
    mcp = tmp_path / "mcp"
    knowledge = tmp_path / "knowledge"
    for directory in (skills, agents, prompts, tools, mcp, knowledge):
        directory.mkdir()

    write(
        skills / "proposal.md",
        """---
name: proposal-skill
description: Proposal skill
enabled: true
---
Analyse the proposal.
""",
    )
    write(
        agents / "analyst.md",
        """---
name: business-analyst
description: Analyst
skills:
  - proposal-skill
knowledgeBases:
  - name: presales-corporate
    usageMode: REFERENCE
enabled: true
---
Act as an analyst.
""",
    )
    write(
        knowledge / "template.md",
        """---
knowledgeBase: presales-corporate
knowledgeBaseDescription: Presales knowledge
documentName: template.md
scope: TENANT
retentionPolicy: PERSISTENT
---
# Standard template

Use this when the customer does not provide one.
""",
    )

    catalog = FakeCatalogService()
    knowledge_service = FakeKnowledgeService()
    loader = MarkdownCatalogLoader(
        catalog,
        FakePromptService(),
        FakeToolService(),
        knowledge_service,
        skills_dir=str(skills),
        agents_dir=str(agents),
        prompts_dir=str(prompts),
        tools_dir=str(tools),
        mcp_servers_dir=str(mcp),
        knowledge_dir=str(knowledge),
    )

    await loader.load()
    await loader.load()

    assert list(knowledge_service.kbs) == ["presales-corporate"]
    kb = knowledge_service.kbs["presales-corporate"]
    assert len(knowledge_service.documents[kb.id]) == 1
    assert knowledge_service.documents[kb.id][0].metadata["bootstrapSource"] == "template.md"

    agent = catalog.agents["business-analyst"]
    assigned = knowledge_service.assignments[agent.id]
    assert len(assigned) == 1
    assert assigned[0]["knowledgeBase"].name == "presales-corporate"
    assert assigned[0]["usageMode"] == "REFERENCE"
