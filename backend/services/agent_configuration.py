"""Validated session-editable agent instructions and registered tool configuration."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

TOOL_DESCRIPTIONS = {
    'search_graph': 'Find resources by identity, keyword and contextual embedding similarity. Use query and optional domain.',
    'inspect_resource': 'Read bounded properties and explicit incident relationships for node_id.',
    'traverse_graph': 'Traverse explicit evidence links for node_id, direction and depth; excludes containment and metadata.',
    'coverage_gaps': 'Find active requirements missing explicit implementation or validation evidence.',
    'similar_resources': 'Compare label and directed-neighbor overlap for node_id; not semantic equivalence.',
}
AgentId = Literal['trace-explorer', 'coverage-reviewer', 'change-analyst']
ToolId = Literal['search_graph', 'inspect_resource', 'traverse_graph', 'coverage_gaps', 'similar_resources']

class AgentConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    system_prompt: str = Field(min_length=1, max_length=12000)
    tools: list[ToolId] = Field(min_length=1, max_length=5)

    @field_validator('system_prompt')
    @classmethod
    def meaningful_prompt(cls, value):
        if not value.strip():
            raise ValueError('System prompt must not be blank')
        return value

    @field_validator('tools')
    @classmethod
    def unique_tools(cls, value):
        if len(set(value)) != len(value):
            raise ValueError('Tools must be unique')
        return value

class ToolConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    description: str = Field(min_length=1, max_length=2000)

    @field_validator('description')
    @classmethod
    def meaningful_description(cls, value):
        if not value.strip():
            raise ValueError('Tool description must not be blank')
        return value

DEFAULT_PROMPTS = {
    'trace-explorer': 'Explore lifecycle traceability. Search resources, inspect properties and traverse directed context. Explain evidence and its limitations.',
    'coverage-reviewer': 'Review explicit implementation and validation gaps. Distinguish absent evidence from failing tests and explain partial provider coverage.',
    'change-analyst': 'Analyze bounded dependencies and resource similarity. Reachability is not causal impact and similarity is not semantic equivalence.',
}

def configured_agent(agent, connection):
    override = getattr(connection, 'agent_configuration', {}).get(agent['id'])
    return {**agent, 'system_prompt': override.system_prompt if override else DEFAULT_PROMPTS[agent['id']],
            'tools': list(override.tools) if override else list(agent['tools'])}
