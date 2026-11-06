
# src/graph_builder.py

from typing import Annotated, List
from typing_extensions import TypedDict
import time

from langgraph.graph import StateGraph, START
from langgraph.types import StreamWriter

from pydantic_ai.usage import UsageLimits
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
)

from agents.assistant import assistant, retrieve_knowledge


MAX_HISTORY_MESSAGES = 7


class ChatbotState(TypedDict):
    latest_user_message: str
    messages: Annotated[List[bytes], lambda x, y: x + y]
    response: str



async def main_assistant(
    state: ChatbotState,
    writer: StreamWriter,
):

    print("\n[1] main_assistant started")

    message_history: list[ModelMessage] = []

    recent_messages = state.get("messages", [])[
        -MAX_HISTORY_MESSAGES:
    ]

    print(f"[2] Previous message records: {len(recent_messages)}")

    for message_row in recent_messages:
        message_history.extend(
            ModelMessagesTypeAdapter.validate_json(message_row)
        )

    print(f"[3] History messages loaded: {len(message_history)}")

    try:

        # ------------------------------------------
        # STEP 1: RETRIEVE COMPANY KNOWLEDGE
        # ------------------------------------------

        print("\n[4] Retrieving company knowledge...")

        user_query = state["latest_user_message"]

        retrieved_context = retrieve_knowledge(user_query)

        # ------------------------------------------
        # STEP 2: BUILD THE PROMPT
        # ------------------------------------------

        if retrieved_context:

            final_prompt = f"""
            CUSTOMER QUESTION:
            {user_query}

            COMPANY DATABASE CONTEXT:
            {retrieved_context}

            INSTRUCTIONS:
            Answer the customer using the company database context.
            Do not invent information.
            Give only the first relevant troubleshooting step.
            """

        else:

             final_prompt = f"""
            CUSTOMER QUESTION:
            {user_query}

            COMPANY DATABASE CONTEXT:
            No relevant technical support information was retrieved.

            INSTRUCTIONS:
            Do not provide a troubleshooting solution from general knowledge.
            Explain that verified company information is unavailable.
            Ask for more details or offer human technician support.
            """

        # ------------------------------------------
        # STEP 3: RUN PYDANTIC AI AGENT
        # ------------------------------------------

        print("\n[5] Sending retrieved context to Groq...")

        result = await assistant.run(
            final_prompt,
            message_history=message_history,
            usage_limits=UsageLimits(request_limit=6),
        )

        response_text = str(result.output)

        print("\n[6] Agent response received!")
        print(response_text)

        writer(response_text)

        # ------------------------------------------
        # STEP 4: SAVE CONVERSATION HISTORY
        # ------------------------------------------

        print("\n[7] Saving conversation history")

        return {
            "messages": [result.new_messages_json()],
            "response": response_text,
        }

    except Exception as e:

        print(
            f"[ERROR] main_assistant failed: "
            f"{type(e).__name__}: {e}"
        )

        raise



def build_graph(checkpointer=None):
    graph_builder = StateGraph(ChatbotState)

    graph_builder.add_node("agent", main_assistant)
    graph_builder.add_edge(START, "agent")

    graph = graph_builder.compile(
        checkpointer=checkpointer
    )

    return graph
