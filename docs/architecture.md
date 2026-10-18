# Architecture

```text
User
 │
 ▼
Streamlit UI
 │
 ├── LLM Adapter ──► OpenAI-compatible API / local fallback
 ├── Interaction State ──► latency / accept-revise-reject / edit similarity
 ├── Over-Reliance Detector ──► transparent heuristic
 ├── Adaptive Intervention ──► reflection prompt
 └── Logging Pipeline ──► CSV → dashboard / evaluation
```
