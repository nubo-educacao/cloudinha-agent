import logging
import sys
import asyncio

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

from src.agent.agent import agent

async def main():
    logger.info(f"Starting agent: {agent.name}")
    print(f"Agent '{agent.name}' is ready.")
    print("Press Ctrl+C to exit.")
    
    # Keep the process alive for Docker/testing purposes
    # In a real deployment, this might be replaced by a server (e.g. FastAPI, MCP)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
