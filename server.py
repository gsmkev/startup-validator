from dotenv import load_dotenv
load_dotenv()

from logging_config import configure_logging

configure_logging()

from tools import mcp


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
