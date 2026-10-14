
from agent import (
    build_reader_agent,
    build_search_agent,
    writer_chain,
    critic_chain
)


def run_research_pipeline(topic: str) -> dict:
    state = {}

    # Step 1 - Search agent
    print("\n" + "=" * 50)
    print("Step 1 - Search agent is working")
    print("=" * 50)

    search_agent = build_search_agent()

    search_result = search_agent.invoke({
        "messages": [
            (
                "user",
                f"Find recent, reliable and detailed information about: {topic}"
            )
        ]
    })

    state["search_result"] = search_result["messages"][-1].content

    print("\nSearch result:\n", state["search_result"])

    # Step 2 - Reader agent
    print("\n" + "=" * 50)
    print("Step 2 - Reader agent is scraping top resources...")
    print("=" * 50)

    reader_agent = build_reader_agent()

    reader_result = reader_agent.invoke({
        "messages": [
            (
                "user",
                f"Based on the following search results about '{topic}', "
                "pick the most relevant URL and scrape it for deeper content.\n\n"
                f"Search Results:\n{state['search_result'][:800]}"
            )
        ]
    })

    state["scraped_content"] = reader_result["messages"][-1].content

    print("\nScraped content:\n", state["scraped_content"])

    # Step 3 - Writer chain
    print("\n" + "=" * 50)
    print("Step 3 - Writer is drafting the report...")
    print("=" * 50)

    research_combined = (
        f"SEARCH RESULT:\n{state['search_result']}\n\n"
        f"DETAILED SCRAPED CONTENT:\n{state['scraped_content']}"
    )

    state["report"] = writer_chain.invoke({
        "topic": topic,
        "research": research_combined
    })

    print("\nFinal report:\n", state["report"])

    # Step 4 - Critic chain
    print("\n" + "=" * 50)
    print("Step 4 - Critic is reviewing the report...")
    print("=" * 50)

    state["feedback"] = critic_chain.invoke({
        "report": state["report"]
    })

    print("\nCritic report:\n", state["feedback"])

    return state


if __name__ == "__main__":
    topic = input("\nEnter your research topic: ")
    result = run_research_pipeline(topic)
