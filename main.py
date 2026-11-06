
import asyncio
import sys
import selectors
import os
import time
from dotenv import load_dotenv

# Load environment variables before importing project modules
load_dotenv()

from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from graph_builder import build_graph


async def run_local_chat(
    graph,
    user_message: str,
    from_number: str,
) -> str:
    """Run the graph and return the assistant's text response."""

    config = {
        "configurable": {
            "thread_id": from_number,
        }
    }

    result = await graph.ainvoke(
        {
            "latest_user_message": user_message,
            "response": "",
        },
        config,
    )

    print("Graph result type:", type(result))

    # Extract only the assistant's response text
    response = result.get("response", "")

    if not response:
        print("Graph result:", result)
        raise RuntimeError(
            "Assistant response is empty. Check graph_builder.py."
        )

    print("Assistant reply:", response)

    return response


async def run_agent(
    user_message: str,
    from_number: str,
) -> str:
    """Run the AI agent with PostgreSQL conversation memory."""

    total_start_time = time.perf_counter()

    conninfo = make_conninfo(
        host=os.getenv("SUPABASE_DB_HOST"),
        dbname=os.getenv("SUPABASE_DB_NAME", "postgres"),
        user=os.getenv("SUPABASE_DB_USER", "postgres"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        port=os.getenv("SUPABASE_DB_PORT", "5432"),
        sslmode="require",
    )

    pool_start_time = time.perf_counter()

    async with AsyncConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,
            "row_factory": dict_row,
        },
    ) as pool:

        async with pool.connection() as conn:
            setup_start_time = time.perf_counter()
            memory = AsyncPostgresSaver(conn)
            await memory.setup()

            print("Memory setup time:",round(time.perf_counter() - setup_start_time, 2), "seconds")

            graph = build_graph(checkpointer=memory)

            agent_start_time = time.perf_counter()

            response = await run_local_chat(
                graph,
                user_message,
                from_number,
            )

            print("Agent execution time:", round(time.perf_counter() - agent_start_time, 2), "seconds")
            print("Total agent processing time:", round(time.perf_counter() - total_start_time, 2), "seconds")

            print("Final agent response:", response)

            return response


async def main_loop():
    from_number = "12222"

    while True:
        try:
            user_input = input("User: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            response = await run_agent(
                user_input,
                from_number,
            )

            print("Assistant:", response)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

        except Exception as e:
            print(f"Error: {e}")

            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Windows-compatible event loop
    with asyncio.Runner(
        loop_factory=lambda: asyncio.SelectorEventLoop(
            selectors.SelectSelector()
        )
    ) as runner:
        runner.run(main_loop())
