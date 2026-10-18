from pathlib import Path
import pandas as pd
p=Path(__file__).parent/'data'/'interaction_logs.csv'
if not p.exists(): print('No interaction_logs.csv yet.')
else:
    df=pd.read_csv(p)
    if df.empty: print('Log is empty.')
    else:
        df['risk_score']=pd.to_numeric(df['risk_score'],errors='coerce')
        print(df.groupby('mode').agg(n=('risk_score','size'),mean_risk=('risk_score','mean'),median_risk=('risk_score','median')))
