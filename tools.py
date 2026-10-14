
from langchain.tools import tool
from tavily import TavilyClient
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rich import print
from urllib.parse import urlparse
import requests
import os

load_dotenv()

tavily = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)


# Tool 1: Search the web
@tool
def web_search(query: str) -> str:
    """Search the web and return relevant titles, URLs and snippets."""

    result = tavily.search(
        query=query,
        max_results=5
    )

    out = []

    for r in result["results"]:
        out.append(
            f"Title: {r['title']}\n"
            f"URL: {r['url']}\n"
            f"Snippet: {r['content'][:300]}"
        )

    return "\n\n------\n\n".join(out)


# Tool 2: Extract text from a webpage
@tool
def scrape_url(url: str) -> str:
    """Fetch a public webpage and extract its title, headings and paragraphs."""

    parsed_url = urlparse(url)

    if parsed_url.scheme not in ("http", "https"):
        return "Error: Please provide a valid HTTP or HTTPS URL."

    if not parsed_url.hostname:
        return "Error: Invalid URL."

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # Remove unnecessary HTML elements
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        title = soup.title.get_text(
            strip=True
        ) if soup.title else "No title found"

        headings = [
            h.get_text(" ", strip=True)
            for h in soup.find_all(["h1", "h2"])
        ]

        paragraphs = [
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")
        ]

        text = "\n".join(paragraphs)

        return (
            f"Title: {title}\n\n"
            f"Headings: {' | '.join(headings[:10])}\n\n"
            f"Page Content:\n{text[:3000]}"
        )

    except requests.RequestException as e:
        return f"Website request failed: {e}"





