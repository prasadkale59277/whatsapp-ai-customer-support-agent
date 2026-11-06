
import asyncio
import selectors
import uvicorn


def main():
    config = uvicorn.Config(
        "api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )

    server = uvicorn.Server(config)

    with asyncio.Runner(
        loop_factory=lambda: asyncio.SelectorEventLoop(
            selectors.SelectSelector()
        )
    ) as runner:
        runner.run(server.serve())


if __name__ == "__main__":
    main()
