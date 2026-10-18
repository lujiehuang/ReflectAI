# ReflectAI

ReflectAI is a minimal research prototype for studying **over-reliance in human–LLM collaboration**.

## Core features
- OpenAI-compatible LLM integration
- local fallback mode
- transparent over-reliance risk heuristic
- adaptive reflection prompts
- structured interaction logging
- baseline vs reflective study conditions
- evaluation dashboard

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional API configuration:
```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4.1-mini"
```

## Research question
Can an interface detect possible over-reliance and intervene without removing user agency?

## Suggested outcomes
acceptance latency, revision amount, decision accuracy, verification behavior, trust, cognitive effort, perceived agency, post-task recall.

## Author
Lujie Huang  
https://lujiehuang.github.io/
