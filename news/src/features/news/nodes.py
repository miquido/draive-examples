from draive import AgentNode

__all__ = [
    "workflow_agent",
]

# to avoid circular dependencies we can define agent
# nodes before providing its implementation
workflow_agent: AgentNode = AgentNode(
    name="workflow",
    description="Manages news preparation",
)
