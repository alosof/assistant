import os

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


def main():
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    query = input("Search query: ")
    response = client.search(
        query=query,
	max_results=10,
        include_domains=["legifrance.gouv.fr"],
    )
    for result in response["results"]:
        print(f"\n--- {result['title']} ---")
        print(result["url"])
        print(result["content"])


if __name__ == "__main__":
    main()
