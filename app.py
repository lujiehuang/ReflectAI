import os, time, hashlib
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests
import streamlit as st

APP_DIR=Path(__file__).parent
DATA_DIR=APP_DIR/'data'; DATA_DIR.mkdir(exist_ok=True)
LOG_FILE=DATA_DIR/'interaction_logs.csv'
FIELDS=['timestamp','session_id','mode','user_query','ai_answer','user_action','acceptance_latency_sec','edited_answer','risk_score','risk_level','reflection_triggered','reflection_response','confidence_cue']

def ensure_log():
    if not LOG_FILE.exists(): pd.DataFrame(columns=FIELDS).to_csv(LOG_FILE,index=False)

def session_id():
    if 'sid' not in st.session_state:
        st.session_state.sid=hashlib.sha1(f'{time.time()}-{os.getpid()}'.encode()).hexdigest()[:10]
    return st.session_state.sid

def local_demo_answer(prompt):
    q=prompt.lower()
    if 'phd' in q or 'career' in q or 'job' in q:
        return 'Separate short-term constraints from long-term goals. Compare funding, supervision, training quality, and desired career outcomes before deciding.'
    if 'ai' in q or 'llm' in q:
        return 'LLM assistance can improve speed and idea generation, but it can also encourage over-reliance. Verify key claims and preserve an opportunity to revise or reject the model output.'
    return 'Here is a concise answer. For an important decision, verify key assumptions and consider at least one alternative interpretation.'

def call_llm(prompt):
    key=os.getenv('OPENAI_API_KEY','').strip(); base=os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1').rstrip('/'); model=os.getenv('OPENAI_MODEL','gpt-4.1-mini')
    if key:
        try:
            r=requests.post(base+'/chat/completions',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':model,'messages':[{'role':'system','content':'You are a concise, careful assistant. State uncertainty explicitly.'},{'role':'user','content':prompt}],'temperature':0.4},timeout=60)
            r.raise_for_status(); return r.json()['choices'][0]['message']['content'].strip()
        except Exception: pass
    return local_demo_answer(prompt)

def similarity(a,b):
    import difflib
    return difflib.SequenceMatcher(None,(a or '').strip(),(b or '').strip()).ratio()

def risk(latency,answer,edited,action):
    score=0.; reasons=[]
    if latency<8: score+=.40; reasons.append('very fast acceptance')
    elif latency<20: score+=.20; reasons.append('fast acceptance')
    sim=similarity(answer,edited)
    if sim>.97: score+=.35; reasons.append('almost no revision')
    elif sim>.85: score+=.20; reasons.append('minimal revision')
    if action=='Accept': score+=.20; reasons.append('explicit acceptance')
    score=min(score,1.0); level='High' if score>=.65 else 'Medium' if score>=.35 else 'Low'
    return score,level,reasons

def cue(): return 'Confidence cue: this prototype does not claim calibrated confidence. Important claims should be independently verified.'
def prompt(reasons): return 'Before accepting the AI response:\n\n1. What assumption might be wrong?\n2. What evidence would change your decision?\n3. Give one alternative or counterargument.\n\nTrigger rationale: '+(', '.join(reasons) if reasons else 'limited independent revision')+'.'
def log(row): ensure_log(); pd.DataFrame([row],columns=FIELDS).to_csv(LOG_FILE,mode='a',header=False,index=False)

st.set_page_config(page_title='ReflectAI',page_icon='🧠',layout='wide')
st.title('🧠 ReflectAI'); st.caption('Adaptive reflection for human–LLM collaboration • research prototype')
with st.sidebar:
    mode=st.radio('Study condition',['Baseline LLM','Reflective LLM']); st.write('Session:',session_id()); st.info('Transparent heuristic detector for research demonstration only.')

t1,t2,t3=st.tabs(['Interaction','Research dashboard','Mechanism'])
with t1:
    query=st.text_area('Ask the AI a question',height=110,placeholder='Example: Should I accept this PhD offer?')
    if st.button('Generate AI response',type='primary',disabled=not query.strip()):
        st.session_state.query=query; st.session_state.answer=call_llm(query); st.session_state.generated_at=time.time(); st.session_state.pop('risk_level',None); st.session_state.pop('pending_log',None)
    if 'answer' in st.session_state:
        st.markdown('### AI response'); st.write(st.session_state.answer); cc=cue(); st.caption(cc)
        st.markdown('### Your decision'); action=st.radio('Action',['Accept','Revise','Reject'],horizontal=True)
        edited=st.text_area('Your final version / reasoning',value=st.session_state.answer if action=='Accept' else '',height=140)
        if st.button('Continue'):
            latency=max(0.,time.time()-st.session_state.generated_at); score,level,reasons=risk(latency,st.session_state.answer,edited,action); triggered=(mode=='Reflective LLM' and level in ['Medium','High'])
            st.session_state.risk_score=score; st.session_state.risk_level=level; st.session_state.reflection_text=prompt(reasons) if triggered else ''
            st.session_state.pending_log={'timestamp':datetime.utcnow().isoformat(timespec='seconds')+'Z','session_id':session_id(),'mode':mode,'user_query':st.session_state.query,'ai_answer':st.session_state.answer,'user_action':action,'acceptance_latency_sec':round(latency,2),'edited_answer':edited,'risk_score':round(score,3),'risk_level':level,'reflection_triggered':triggered,'reflection_response':'','confidence_cue':cc}
        if 'risk_level' in st.session_state:
            c1,c2=st.columns(2); c1.metric('Over-reliance risk',st.session_state.risk_level); c2.metric('Heuristic score',f"{st.session_state.risk_score:.2f}")
            if st.session_state.get('reflection_text'):
                st.warning(st.session_state.reflection_text); rr=st.text_area('Your reflection',height=100)
                if st.button('Submit reflection and save'):
                    row=dict(st.session_state.pending_log); row['reflection_response']=rr; log(row); st.success('Interaction saved.')
            elif st.session_state.get('pending_log') and st.button('Save interaction'):
                log(st.session_state.pending_log); st.success('Interaction saved.')
with t2:
    ensure_log(); df=pd.read_csv(LOG_FILE)
    if df.empty: st.info('No logged interactions yet.')
    else:
        df['risk_score']=pd.to_numeric(df['risk_score'],errors='coerce'); c1,c2,c3=st.columns(3); c1.metric('Interactions',len(df)); c2.metric('Mean risk',f"{df['risk_score'].mean():.2f}"); c3.metric('Reflection triggers',int(df['reflection_triggered'].astype(str).str.lower().eq('true').sum())); st.dataframe(df,use_container_width=True)
        st.dataframe(df.groupby('mode').agg(n=('risk_score','size'),mean_risk=('risk_score','mean'),median_risk=('risk_score','median')).reset_index(),use_container_width=True)
        st.download_button('Download logs as CSV',df.to_csv(index=False).encode('utf-8'),'reflectai_interaction_logs.csv','text/csv')
with t3:
    st.markdown('''### Mechanism
1. User asks an LLM.
2. Interface observes acceptance latency, revision amount, and accept/revise/reject behavior.
3. A transparent heuristic estimates over-reliance risk.
4. Reflective mode triggers an intervention for medium/high risk.
5. The interaction is logged for evaluation.

### What this demonstrates
- system implementation
- LLM integration
- adaptive interface logic
- data logging pipeline
- evaluation-ready experimental conditions

A research-grade version could replace the heuristic with a learned model using richer interaction traces, uncertainty calibration, eye tracking, keystroke dynamics, or multimodal signals.''')
