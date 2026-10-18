import os
import time
import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from core import assess_overreliance, build_reflection_prompt, revision_delta, should_trigger

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LOG_FILE = DATA_DIR / "interaction_logs.csv"

FIELDS = [
    "timestamp","session_id","condition","user_query","ai_answer","user_action",
    "acceptance_latency_sec","edited_answer","revision_delta","risk_score","risk_level",
    "reflection_triggered","reflection_response","confidence_cue"
]


def ensure_log():
    if not LOG_FILE.exists():
        pd.DataFrame(columns=FIELDS).to_csv(LOG_FILE, index=False)


def session_id():
    if "sid" not in st.session_state:
        seed = f"{time.time()}-{os.getpid()}"
        st.session_state.sid = hashlib.sha1(seed.encode()).hexdigest()[:10]
    return st.session_state.sid


def local_demo_answer(prompt: str) -> str:
    q = prompt.lower()
    if "phd" in q or "career" in q or "job" in q:
        return (
            "Separate short-term constraints from long-term goals. Compare funding, supervision, "
            "training quality, and desired career outcomes before deciding."
        )
    if "ai" in q or "llm" in q:
        return (
            "LLM assistance can improve speed and idea generation, but it can also encourage "
            "over-reliance. Verify key claims and preserve an opportunity to revise or reject the output."
        )
    return (
        "Here is a concise answer. For an important decision, verify key assumptions and consider "
        "at least one alternative interpretation."
    )


def call_llm(prompt: str) -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if key:
        try:
            r = requests.post(
                base + "/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are concise and careful. State uncertainty explicitly."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                },
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
    return local_demo_answer(prompt)


def confidence_cue() -> str:
    return (
        "Confidence cue: this prototype does not claim calibrated confidence. "
        "Important factual or high-stakes claims should be independently verified."
    )


def save_row(row: dict):
    ensure_log()
    pd.DataFrame([row], columns=FIELDS).to_csv(LOG_FILE, mode="a", header=False, index=False)


st.set_page_config(page_title="ReflectAI", page_icon="🧠", layout="wide")
st.title("🧠 ReflectAI")
st.caption("Adaptive reflection for human–LLM collaboration • research prototype")

with st.sidebar:
    condition = st.radio(
        "Experimental condition",
        ["Baseline", "Static Reflection", "Adaptive Reflection"],
        help=(
            "Baseline: no reflection intervention. Static: always reflect. "
            "Adaptive: reflect only when behavioral signals indicate medium/high reliance risk."
        ),
    )
    st.write("Session:", session_id())
    st.info("The detector is an interpretable research-demo heuristic, not a diagnostic instrument.")

interaction_tab, dashboard_tab, mechanism_tab = st.tabs(
    ["Interaction", "Research dashboard", "Mechanism"]
)

with interaction_tab:
    query = st.text_area(
        "Ask the AI a question",
        height=110,
        placeholder="Example: Should I accept this PhD offer?",
    )

    if st.button("Generate AI response", type="primary", disabled=not query.strip()):
        st.session_state.query = query
        st.session_state.answer = call_llm(query)
        st.session_state.generated_at = time.time()
        for key in ["assessment", "pending_log", "reflection_text"]:
            st.session_state.pop(key, None)

    if "answer" in st.session_state:
        st.markdown("### AI response")
        st.write(st.session_state.answer)
        cue = confidence_cue()
        st.caption(cue)

        st.markdown("### Your decision")
        action = st.radio("Action", ["Accept", "Revise", "Reject"], horizontal=True)
        edited = st.text_area(
            "Your final version / reasoning",
            value=st.session_state.answer if action == "Accept" else "",
            height=140,
        )

        if st.button("Continue"):
            latency = max(0.0, time.time() - st.session_state.generated_at)
            assessment = assess_overreliance(
                latency_seconds=latency,
                ai_answer=st.session_state.answer,
                edited_answer=edited,
                action=action,
            )
            triggered = should_trigger(condition, assessment)
            st.session_state.assessment = assessment
            st.session_state.reflection_text = (
                build_reflection_prompt(assessment.reasons) if triggered else ""
            )
            st.session_state.pending_log = {
                "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "session_id": session_id(),
                "condition": condition,
                "user_query": st.session_state.query,
                "ai_answer": st.session_state.answer,
                "user_action": action,
                "acceptance_latency_sec": round(latency, 2),
                "edited_answer": edited,
                "revision_delta": revision_delta(st.session_state.answer, edited),
                "risk_score": assessment.score,
                "risk_level": assessment.level,
                "reflection_triggered": triggered,
                "reflection_response": "",
                "confidence_cue": cue,
            }

        if "assessment" in st.session_state:
            a = st.session_state.assessment
            c1, c2, c3 = st.columns(3)
            c1.metric("Reliance-risk level", a.level)
            c2.metric("Heuristic score", f"{a.score:.2f}")
            c3.metric("Condition", condition)

            if st.session_state.get("reflection_text"):
                st.warning(st.session_state.reflection_text)
                rr = st.text_area(
                    "Your reflection",
                    placeholder="State one assumption, counterargument, or alternative before continuing.",
                    height=100,
                )
                if st.button("Submit reflection and save"):
                    row = dict(st.session_state.pending_log)
                    row["reflection_response"] = rr
                    save_row(row)
                    st.success("Interaction saved.")
            elif st.session_state.get("pending_log"):
                if st.button("Save interaction"):
                    save_row(st.session_state.pending_log)
                    st.success("Interaction saved.")

with dashboard_tab:
    ensure_log()
    df = pd.read_csv(LOG_FILE)
    if df.empty:
        st.info("No logged interactions yet.")
    else:
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
        df["acceptance_latency_sec"] = pd.to_numeric(df["acceptance_latency_sec"], errors="coerce")
        df["revision_delta"] = pd.to_numeric(df["revision_delta"], errors="coerce")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Interactions", len(df))
        c2.metric("Mean risk", f"{df['risk_score'].mean():.2f}")
        c3.metric("Mean revision delta", f"{df['revision_delta'].mean():.2f}")
        c4.metric(
            "Reflection triggers",
            int(df["reflection_triggered"].astype(str).str.lower().eq("true").sum()),
        )

        st.markdown("### Condition summary")
        summary = (
            df.groupby("condition", dropna=False)
            .agg(
                n=("risk_score", "size"),
                mean_risk=("risk_score", "mean"),
                median_latency=("acceptance_latency_sec", "median"),
                mean_revision=("revision_delta", "mean"),
            )
            .reset_index()
        )
        st.dataframe(summary, use_container_width=True)

        st.markdown("### Interaction records")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "Download logs as CSV",
            df.to_csv(index=False).encode("utf-8"),
            "reflectai_interaction_logs.csv",
            "text/csv",
        )

with mechanism_tab:
    st.markdown(
        """
### Three-condition experimental logic

**Baseline**
- LLM response + verification cue
- no reflection intervention

**Static Reflection**
- every interaction receives the same reflection prompt
- useful as a control for the *presence* of reflection

**Adaptive Reflection**
- behavioral signals are assessed after the user's initial response
- only medium/high-risk interactions receive reflection
- useful for testing whether targeted friction can preserve agency while reducing passive acceptance

### Current behavioral signals

- acceptance latency
- amount of revision relative to the AI answer
- accept / revise / reject action

### Research question

Can an adaptive interface reduce uncritical reliance on LLM outputs while imposing less unnecessary friction than a static reflection prompt?

### Next technical step

Replace the hand-crafted heuristic with a learned predictor trained on interaction traces and validated against task accuracy, verification behavior, and user-reported reliance.
"""
    )
