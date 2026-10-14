# 🔎 AI Research Assistant

> **A multi-agent AI pipeline that transforms any topic into a fully sourced, reviewed research report — powered by MistralAI, Tavily, and Streamlit.**

---

## 📌 Overview

**AI Research Assistant** is an agentic research system that automates the entire research workflow:

1. 🔍 **Search** the web for relevant, up-to-date information
2. 📄 **Scrape** the most relevant source for in-depth content
3. ✍️ **Write** a structured, professional research report
4. 🧑‍⚖️ **Critique** the report with an AI quality review and score

All stages run automatically through a **4-stage multi-agent pipeline** with a polished **Streamlit web UI**.

---

## 🗂️ Project Structure

```
Ai_Assistent/
│
├── app.py          # Streamlit web interface — dashboard, forms, progress tracking, result rendering
├── pipeline.py     # Orchestrator — runs the 4-stage pipeline sequentially
├── agent.py        # Agent definitions — Search Agent, Reader Agent, Writer Chain, Critic Chain
├── tools.py        # LangChain tools — web_search (Tavily) and scrape_url (BeautifulSoup)
├── .env            # API keys (not committed to version control)
└── README.md       # This file
```

---

## 🧠 Architecture

```
User Input (Topic)
       │
       ▼
┌─────────────────┐
│  Search Agent   │  ← Uses Tavily API to find top 5 results (titles, URLs, snippets)
└────────┬────────┘
         │ search_result
         ▼
┌─────────────────┐
│  Reader Agent   │  ← Picks the best URL, scrapes it with BeautifulSoup
└────────┬────────┘
         │ scraped_content
         ▼
┌─────────────────┐
│  Writer Chain   │  ← Combines search + scraped content → structured report (Intro, Findings, Conclusion, Sources)
└────────┬────────┘
         │ report
         ▼
┌─────────────────┐
│  Critic Chain   │  ← Reviews the report: Score /10, Strengths, Areas to Improve, Verdict
└────────┬────────┘
         │ feedback
         ▼
  Streamlit Dashboard
  (Report | Search | Reader | Critic tabs)
```

---

## ⚙️ How It Works

### Stage 1 — Search Agent (`agent.py` + `tools.py`)
- Built with `create_agent` from LangChain, powered by **MistralAI `ministral-8b-2512`**
- Uses the `web_search` tool backed by **Tavily API**
- Returns top 5 results: **title**, **URL**, and **snippet (300 chars)**

### Stage 2 — Reader Agent (`agent.py` + `tools.py`)
- Uses the `scrape_url` tool to fetch and parse a webpage
- Removes `<script>`, `<style>`, `<nav>`, `<footer>` tags
- Extracts: **page title**, **top 10 headings**, **paragraph content (up to 3 000 chars)**

### Stage 3 — Writer Chain (`agent.py`)
- LangChain chain: `ChatPromptTemplate | MistralAI LLM | StrOutputParser`
- Combines search result + scraped content into one research input
- Produces a structured report:
  - Introduction
  - Key Findings (minimum 3 well-explained points)
  - Conclusion
  - Sources (all URLs found in the research)

### Stage 4 — Critic Chain (`agent.py`)
- Evaluates the written report strictly
- Outputs a fixed-format review:
  ```
  Score: X/10
  Strengths: ...
  Areas to Improve: ...
  One line verdict: ...
  ```

---

## 🖥️ Streamlit Dashboard (`app.py`)

| Feature | Details |
|---|---|
| **Live progress bar** | Shows 4 pipeline stages: Waiting → Running → Complete / Failed |
| **Tabbed results** | Final Report · Search Results · Scraped Content · Critic Feedback |
| **Critic score metric** | Displayed prominently at the top of results |
| **Download report** | Save the final report as a `.md` file |
| **Copy report** | In-browser copy via code block |
| **Source links** | Clickable links to every cited URL |
| **Error handling** | Friendly messages for timeouts, rate limits, auth failures, missing packages |
| **Retry button** | Re-run the last failed topic without re-entering it |
| **Partial results** | Shows whatever the pipeline completed before a failure |

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Ai_Assistent
```

### 2. Install Dependencies

```bash
pip install streamlit langchain langchain-mistralai langchain-core \
            tavily-python beautifulsoup4 requests python-dotenv rich
```

### 3. Configure API Keys

Create a `.env` file in the project root:

```env
MISTRAL_API_KEY=your_mistral_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

> **Where to get keys:**
> - MistralAI API key → [console.mistral.ai](https://console.mistral.ai)
> - Tavily API key → [app.tavily.com](https://app.tavily.com)

### 4. Run the App

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

### (Optional) Run the Pipeline from the Terminal

```bash
python pipeline.py
```

You'll be prompted to enter a research topic. The pipeline runs and prints output at each stage.

---

## 📋 Requirements

| Dependency | Purpose |
|---|---|
| `streamlit` | Web dashboard UI |
| `langchain` | Agent framework and tool definitions |
| `langchain-mistralai` | MistralAI LLM integration |
| `langchain-core` | Prompt templates and output parsers |
| `tavily-python` | Tavily web search client |
| `beautifulsoup4` | HTML parsing for web scraping |
| `requests` | HTTP requests for the scraper |
| `python-dotenv` | `.env` file loading |
| `rich` | Colored terminal output |

---

## 📄 Example Output

**Topic:** `"Compare vector databases for a production RAG application"`

The system will produce:
- ✅ A report with **Introduction**, **Key Findings**, **Conclusion**, **Sources**
- ✅ A critic review with a **score out of 10**, **strengths**, and **improvements**
- ✅ Clickable source links from real web pages

---

## 🔐 Security Notes

- Your `.env` file is **never** shown to the user in the UI — errors are sanitized before display
- The `scrape_url` tool only accepts valid `http://` and `https://` URLs
- API keys are loaded using `python-dotenv` and never hard-coded

---

## 🛠️ Customization

| What to change | Where |
|---|---|
| LLM model | `agent.py` → `ChatMistralAI(model="...")` |
| Number of search results | `tools.py` → `max_results=5` |
| Scraped content length | `tools.py` → `text[:3000]` |
| Report structure / style | `agent.py` → `writer_prompt` |
| Critic evaluation criteria | `agent.py` → `critic_prompt` |

---

## 📝 License

This project is open source and free to use for learning and personal projects.
