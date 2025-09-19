import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2anet.executors.langgraph import LangGraphAgentExecutor
from a2anet.types.langgraph import StructuredResponse
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from starlette.applications import Starlette

SYSTEM_INSTRUCTION: str = (
    "You are a helpful assistant that can search the web with the Tavily API and answer questions about the results.\n"
    "You should only respond to messages that can be answered by searching the web, and if the user's most recent message doesn't contain a question, or contains a question that can't be answered by searching the web, you should explain that to the user and ask them to try again with an appropriate query.\n"
    "If the `tavily_search` tool returns insufficient results, you should explain that to the user and ask them to try again with a more specific query.\n"
    "You can use markdown format to format your responses."
)

RESPONSE_FORMAT_INSTRUCTION: str = (
    "You are an expert A2A protocol agent.\n"
    "Your task is to read through all previous messages thoroughly and determine what the state of the task is.\n"
    "The state of the task should be:\n"
    "- 'completed' if the user's most recent message contains a question that can be answered by searching the web, the `tavily_search` tool has been called, and the results are sufficient to answer the user's question.\n"
    "- 'failed' if the user's most recent message contains a question that can be answered by searching the web, the `tavily_search` tool has been called, and the results are insufficient to answer the user's question.\n"
    "- 'rejected' if the user's most recent message doesn't contain a question or contains a question that can't be answered by searching the web.\n"
    "If the task is 'completed', set 'task_state' to 'completed' and include at least one artifact in 'artifacts'.\n"
    "If the task is not 'completed', do not include any artifacts."
)

graph = create_react_agent(
    model="anthropic:claude-sonnet-4-20250514",
    tools=[TavilySearch(max_results=2)],
    checkpointer=MemorySaver(),
    prompt=SYSTEM_INSTRUCTION,
    response_format=(RESPONSE_FORMAT_INSTRUCTION, StructuredResponse),
)

agent_executor: LangGraphAgentExecutor = LangGraphAgentExecutor(graph)

# Get port from environment variable
port: int = int(os.getenv("PORT"))
# Get service URL for agent card (Cloud Run will provide this)
service_url: str = os.getenv("SERVICE_URL", f"http://localhost:{port}")

agent_card: AgentCard = AgentCard(
    name="Tavily Agent",
    icon_url="https://raw.githubusercontent.com/a2anet/tavily-agent/refs/heads/main/tavily_logo.jpeg",
    description="Search the web with the Tavily API and answer questions about the results.",
    url=service_url,
    version="1.0.0",
    defaultInputModes=["text/plain"],
    defaultOutputModes=["text/plain", "application/json"],
    capabilities=AgentCapabilities(),
    skills=[AgentSkill(
        id="search-web",
        name="Search Web",
        description="Search the web with the Tavily API and answer questions about the results.",
        tags=["search", "web", "tavily"],
        examples=["Who is Leo Messi?"],
    )],
)

request_handler: DefaultRequestHandler = DefaultRequestHandler(
    agent_executor=agent_executor, task_store=InMemoryTaskStore()
)

server: A2AStarletteApplication = A2AStarletteApplication(
    agent_card=agent_card, http_handler=request_handler
)

app: Starlette = server.build()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
