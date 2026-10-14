"""Native Streamlit dashboard for the existing four-stage research pipeline."""
import inspect
import json
import re
import time
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st
from dotenv import load_dotenv

STAGES = ("Search", "Reader", "Writer", "Critic")


def text_of(value):
    """Support strings, AIMessage objects, text blocks and structured outputs."""
    if value is None:
        return ""
    if hasattr(value, "content"):
        return text_of(value.content)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("text", "content", "report", "feedback", "output"):
            if key in value:
                return text_of(value[key])
        return json.dumps(dict(value), ensure_ascii=False, indent=2, default=str)
    if isinstance(value, (list, tuple)):
        # Non-text AI content (images/tool blocks) is not a research report.
        parts = [text_of(item) for item in value
                 if not isinstance(item, Mapping)
                 or item.get("type", "text") in ("text", "output_text")]
        return "\n\n".join(part for part in parts if part.strip())
    return str(value)


def feedback_parts(value):
    """Extract only scores and sections explicitly provided by the critic."""
    raw = text_of(value)
    data = value if isinstance(value, Mapping) else None
    if data is None:
        try:
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
            decoded = json.loads(candidate)
            if isinstance(decoded, dict):
                data = decoded
        except (ValueError, TypeError):
            pass
    score = None
    if data:
        for key in ("score", "overall_score", "rating"):
            if key in data:
                match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:/\s*10)?\s*", str(data[key]))
                if match:
                    score = float(match.group(1))
                break
    if score is None:
        match = re.search(r"(?i)\b(?:overall\s+)?(?:score|rating)\b[^\d\n]{0,20}(\d+(?:\.\d+)?)(?:\s*(?:/|out of)\s*(\d+(?:\.\d+)?))?", raw)
        if match:
            if match.group(2) is None or float(match.group(2)) == 10:
                score = float(match.group(1))
    if score is not None and not 0 <= score <= 10:
        score = None

    def section(keys, heading):
        if data:
            for key in keys:
                if key in data:
                    val = data[key]
                    return "\n".join("- " + text_of(v) for v in val) if isinstance(val, list) else text_of(val)
        # Heading-aware fallback; raw feedback is always available below.
        lines = raw.splitlines()
        selected = []
        active = False
        for line in lines:
            clean = line.strip().strip("#* ").rstrip(":")
            if re.fullmatch(heading, clean, flags=re.I):
                active = True
                continue
            if active and (line.startswith("#") or re.fullmatch(
                    r"(?:\*\*)?(?:strengths|areas for improvement|improvements|weaknesses|recommendations|score|overall score|verdict)(?:\*\*)?:?", line.strip(), re.I)):
                break
            if active:
                selected.append(line)
        return "\n".join(selected).strip()

    return score, section(("strengths",), "strengths"), section(
        ("areas_for_improvement", "improvements", "weaknesses"),
        "areas for improvement|improvements|weaknesses"), raw


def source_urls(result):
    """List cited HTTP(S) links, deduplicated without fetching any URL."""
    urls = []

    def visit(value):
        if hasattr(value, "content"):
            visit(value.content)
        elif isinstance(value, Mapping):
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            for match in re.findall(r"https?://[^\s<>\"\[\]]+", value):
                url = match.rstrip(".,;:!?)}`*'")
                try:
                    parsed = urlsplit(url)
                    if parsed.hostname and not parsed.username and url not in urls:
                        urls.append(url)
                except ValueError:
                    continue

    for key in ("search_result", "scraped_content", "report", "sources"):
        visit(result.get(key))
    return urls


def safe_error(exc):
    """Show helpful errors without echoing provider payloads or credentials."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()  # Classification only; never render raw exceptions.
    if isinstance(exc, ModuleNotFoundError):
        module = exc.name or "an agent dependency"
        if module in ("agent", "agents", "tools", "pipeline"):
            return f"Missing project module: {module}.py. Place your existing project files beside app.py."
        return f"Missing Python package: {module}. Install your existing project requirements."
    if "timeout" in name or "timed out" in message:
        return "A research service timed out. Check your connection and provider availability, then retry."
    if "ratelimit" in name or "429" in message or "rate limit" in message:
        return "Your AI or search provider is rate limited. Wait for the provider's retry window, then retry."
    if "authentication" in name or "401" in message or "api key" in message:
        return "Provider authentication failed. Check the API keys in your existing .env file."
    if "connection" in name:
        return "Unable to reach a research service. Check your network and retry."
    if isinstance(exc, ValueError) and message.startswith(("search returned", "reader returned", "writer returned")):
        return str(exc)
    return "Research could not finish. Check your agent dependencies, provider configuration and service availability, then retry."


def show_progress(placeholder):
    with placeholder.container():
        completed = sum(st.session_state.stage_states[s] == "Complete" for s in STAGES)
        st.progress(completed / len(STAGES), text=f"{completed} of 4 stages complete")
        with st.expander("Pipeline stages", expanded=True):
            for number, stage in enumerate(STAGES, 1):
                state = st.session_state.stage_states[stage]
                symbol = {"Complete": "✓", "Running": "◉", "Failed": "!", "Waiting": "○"}[state]
                st.write(f"{symbol}  {number}. **{stage}** · {state}")


def run_research(topic, placeholder):
    st.session_state.error = None
    st.session_state.attempt_topic = topic
    st.session_state.partial_result = {}
    st.session_state.stage_states = dict.fromkeys(STAGES, "Waiting")
    st.session_state.copy_open = False
    started = time.monotonic()
    current = None
    with st.status("Preparing research…", expanded=True) as status:
        try:
            # Load existing secrets before importing the agent module.
            load_dotenv(Path(__file__).parent / ".env", override=False)
            from pipeline import run_research_pipeline

            def progress(stage, event, snapshot):
                nonlocal current
                current = stage
                st.session_state.partial_result = snapshot
                st.session_state.stage_states[stage] = "Running" if event == "started" else "Complete"
                status.update(label=f"{stage} {'is working…' if event == 'started' else 'complete'}")
                show_progress(placeholder)

            with st.spinner("Your research team is working. This may take a few minutes."):
                if "on_progress" in inspect.signature(run_research_pipeline).parameters:
                    result = run_research_pipeline(topic, on_progress=progress)
                else:
                    # Works with the unmodified original; no simulated stage timing.
                    status.update(label="Research running · stage tracking requires the supplied pipeline update")
                    result = run_research_pipeline(topic)
                if not isinstance(result, Mapping):
                    raise TypeError("Pipeline must return a dictionary.")
                if not text_of(result.get("report")).strip():
                    raise ValueError("Writer returned an empty report. Retry research.")
            st.session_state.result = dict(result)
            st.session_state.result_topic = topic
            st.session_state.elapsed = time.monotonic() - started
            st.session_state.finished_at = datetime.now().strftime("%d %b %Y · %H:%M")
            st.session_state.stage_states = dict.fromkeys(STAGES, "Complete")
            status.update(label="Research complete", state="complete", expanded=False)
        except Exception as exc:
            if current:
                st.session_state.stage_states[current] = "Failed"
            st.session_state.error = safe_error(exc)
            status.update(label="Research interrupted", state="error", expanded=False)
    show_progress(placeholder)


def render_result(result, topic, partial=False):
    report = text_of(result.get("report"))
    score, strengths, improvements, raw_feedback = feedback_parts(result.get("feedback"))
    urls = source_urls(result)
    st.subheader("Research workspace" if not partial else "Completed work from this attempt")
    st.caption(f"Topic: {topic}")
    if not partial:
        st.caption(f"Completed {st.session_state.finished_at} · {st.session_state.elapsed:.1f} seconds · {len(urls)} cited links")
    st.metric("Critic score", f"{score:g} / 10" if score is not None else "Not provided")
    report_tab, search_tab, reader_tab, critic_tab = st.tabs(
        ["Final report", "Search results", "Scraped content", "Critic feedback"])
    with report_tab:
        if report.strip():
            if partial:
                st.warning("Draft report: this attempt did not complete all four stages.")
            with st.container(border=True):
                st.markdown(report)
            with st.container(horizontal=True):
                st.download_button("Download Report", report, file_name="research_report.md",
                                   mime="text/markdown", on_click="ignore", key=f"download_{partial}")
                if st.button("Copy Report", key=f"copy_{partial}"):
                    st.session_state.copy_open = not st.session_state.copy_open
            if st.session_state.copy_open:
                st.caption("Use the copy icon at the top-right of the block to copy the full report.")
                st.code(report, language=None, wrap_lines=True)
        else:
            st.info("No report available yet.")
    with search_tab:
        content = text_of(result.get("search_result"))
        if content.strip():
            st.markdown(content)
        else:
            st.info("No search results were returned. Try a more specific topic.")
    with reader_tab:
        content = text_of(result.get("scraped_content"))
        if content.strip():
            st.markdown(content)
        else:
            st.info("No scraped content available. A source may block automated reading.")
    with critic_tab:
        st.subheader("Strengths")
        if strengths:
            st.markdown(strengths)
        else:
            st.caption("No separate strengths section was identified. See the complete feedback below.")
        st.subheader("Areas for improvement")
        if improvements:
            st.markdown(improvements)
        else:
            st.caption("No separate improvement section was identified.")
        with st.expander("Complete critic feedback", expanded=not (strengths or improvements)):
            if raw_feedback.strip():
                st.markdown(raw_feedback)
            else:
                st.info("The critic did not provide feedback.")
    with st.expander(f"Sources · {len(urls)} cited links", expanded=st.session_state.show_sources):
        st.caption("Links mentioned in pipeline output; they have not been independently verified.")
        for number, url in enumerate(urls, 1):
            st.link_button(f"{number}. {urlsplit(url).hostname}", url, help=url)
        if not urls:
            st.info("No source URLs were included in the returned content.")
    extra = {key: value for key, value in result.items()
             if key not in ("search_result", "scraped_content", "report", "feedback", "sources")}
    if extra:
        with st.expander("Additional pipeline output"):
            for key, value in extra.items():
                st.write(str(key))
                st.text(text_of(value))


def main():
    st.set_page_config(page_title="AI Research Assistant", page_icon="🔎", layout="wide")
    defaults = {"result": None, "error": None, "partial_result": {}, "copy_open": False,
                "attempt_topic": "", "stage_states": dict.fromkeys(STAGES, "Waiting")}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    with st.sidebar:
        st.title("🔎 Research Studio")
        with st.expander("About", expanded=True):
            st.write("Turn a question into a sourced report using your existing AI research team.")
        with st.expander("Workflow", expanded=True):
            st.write("1. **Search** discovers relevant information.\n\n2. **Reader** scrapes a selected source.\n\n3. **Writer** drafts the report.\n\n4. **Critic** reviews its quality.")
        with st.expander("Settings", expanded=True):
            st.checkbox("Expand source links", value=True, key="show_sources")
            st.caption("Models, search limits and provider timeouts are controlled by your existing agents and tools.")
        st.caption("Results stay in this browser session during normal interactions. A browser refresh may clear them.")
    st.caption("RESEARCH STUDIO / MULTI-AGENT INTELLIGENCE")
    st.title("AI Research Assistant")
    st.write("Explore a topic, read relevant sources, and generate a report with an independent AI quality review.")
    with st.container(border=True):
        with st.form("research_form"):
            topic = st.text_area("What would you like to research?", height=150, key="topic_input",
                                 placeholder="Example: Compare vector databases for a production RAG application.",
                                 help="Include the subject, timeframe and key questions for a focused report.")
            submitted = st.form_submit_button("Start Research", type="primary", width="stretch")
    progress_placeholder = st.empty()
    show_progress(progress_placeholder)
    if submitted:
        if not topic.strip():
            st.warning("Enter a research topic before starting.")
        else:
            run_research(topic.strip(), progress_placeholder)
    if st.session_state.error:
        st.error(st.session_state.error)
        st.caption(f"Failed attempt: {st.session_state.attempt_topic}")
        if st.button("Retry Research", type="primary"):
            run_research(st.session_state.attempt_topic, progress_placeholder)
            st.rerun()
        if st.session_state.error and st.session_state.partial_result:
            render_result(st.session_state.partial_result, st.session_state.attempt_topic, partial=True)
    if st.session_state.result:
        if st.session_state.error:
            st.info("Your last completed research is preserved below.")
        render_result(st.session_state.result, st.session_state.result_topic)
    elif not st.session_state.error:
        with st.container(border=True):
            st.subheader("Your next report starts with a question")
            st.write("Enter a clear topic above. Your report, research notes, sources and quality feedback will appear here.")


if __name__ == "__main__":
    main()
