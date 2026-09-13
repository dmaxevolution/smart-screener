#!/usr/bin/env python3
import json, os, math, tempfile, time
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

DB_FILE='emiten.json'; OUT_FILE='data.json'; MIN_SUCCESS_RATIO=.70

def clean(x):
 if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)): return [clean(v) for v in x]
 if isinstance(x,np.integer): return int(x)
 if isinstance(x,(np.floating,float)):
  v=float(x); return None if math.isnan(v) or math.isinf(v) else v
 return x

def dl(symbol,period,interval):
 for _ in range(3):
  try:
   d=yf.download(symbol,period=period,interval=interval,auto_adjust=True,progress=False,threads=False,timeout=20)
   if d is not None and not d.empty:
    if isinstance(d.columns,pd.MultiIndex): d.columns=d.columns.get_level_values(0)
    return d.dropna()
  except Exception: pass
  time.sleep(1)
 return None

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n=14):
 d=s.diff(); u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean(); return 100-(100/(1+u/dn.replace(0,np.nan)))
def macd(s):
 m=ema(s,12)-ema(s,26); sig=ema(m,9); return m,sig,m-sig

def analyze(df):
 if df is None or len(df)<30: raise ValueError('insufficient data')
 c=pd.to_numeric(df.Close,errors='coerce'); e20,e50=ema(c,20),ema(c,50); e200=ema(c,200) if len(c)>=200 else pd.Series([np.nan]*len(c),index=c.index)
 rr=rsi(c); m,ms,mh=macd(c); q=df.iloc[-1]
 close=float(c.iloc[-1]); prev=float(c.iloc[-2]) if len(c)>1 else close
 score=50
 score += 12 if close>e20.iloc[-1]>e50.iloc[-1] else -10
 if pd.notna(e200.iloc[-1]): score += 8 if close>e200.iloc[-1] else -7
 if 50<=rr.iloc[-1]<=70: score+=10
 elif rr.iloc[-1]<35 or rr.iloc[-1]>80: score-=8
 score += 8 if m.iloc[-1]>ms.iloc[-1] else -6
 score=max(0,min(100,round(score)))
 trend='BULLISH' if close>e20.iloc[-1]>e50.iloc[-1] else ('BEARISH' if close<e20.iloc[-1]<e50.iloc[-1] else 'SIDEWAYS')
 return {'close':close,'change_pct':(close-prev)/prev*100 if prev else 0,'open':float(q.Open),'high':float(q.High),'low':float(q.Low),'volume':float(q.Volume or 0),'ema20':float(e20.iloc[-1]),'ema50':float(e50.iloc[-1]),'ema200':float(e200.iloc[-1]) if pd.notna(e200.iloc[-1]) else None,'rsi':float(rr.iloc[-1]),'macd':float(m.iloc[-1]),'macd_signal':float(ms.iloc[-1]),'macd_hist':float(mh.iloc[-1]),'trend':trend,'score':score,'support':float(df.Low.tail(20).min()),'resistance':float(df.High.tail(20).max())}

def sig(score): return 'ELITE BUY' if score>=90 else 'STRONG BUY' if score>=80 else 'BUY' if score>=70 else 'WATCHLIST' if score>=60 else 'WAIT' if score>=50 else 'AVOID'

def stock(row):
 t=str(row['ticker']).upper().replace('.JK',''); d=dl(t+'.JK','2y','1d'); a=analyze(d)
 # SAFE: intraday only last 60 days; failure does not fail daily analysis
 h=dl(t+'.JK','60d','1h'); hdata=analyze(h) if h is not None and len(h)>=30 else {'status':'unavailable'}
 score=a['score']; close=a['close']; risk=max(close*.02, close-a['support']); sl=max(a['support'],close-risk); tp1=close+(close-sl)*2; tp2=close+(close-sl)*3
 return {'ticker':t,'sector':row.get('sector','IDX'),'close':close,'change_pct':a['change_pct'],'professional_score':score,'entry_probability':score,'signal_strength':score,'signal':sig(score),'strategy':'TREND FOLLOWING' if a['trend']=='BULLISH' else 'WAIT / NO TRADE','mtf_alignment':a['trend'],'ema20':a['ema20'],'ema50':a['ema50'],'ema200':a['ema200'],'rsi':a['rsi'],'macd':a['macd'],'macd_signal':a['macd_signal'],'risk_plan':{'entry':close,'stop_loss':sl,'tp1':tp1,'tp2':tp2},'timeframes':{'daily':a,'1h':hdata}}

def main():
 with open(DB_FILE,encoding='utf-8') as f: rows=[x for x in json.load(f).get('emiten',[]) if x.get('active',True) and x.get('ticker')]
 old={}
 try:
  with open(OUT_FILE,encoding='utf-8') as f: old={str(x.get('ticker','')).upper():x for x in json.load(f).get('all_stocks',[])}
 except Exception: pass
 stocks=[]; failed=[]; fresh=0
 for r in rows:
  t=str(r['ticker']).upper().replace('.JK','')
  try: stocks.append(stock(r)); fresh+=1; print('OK',t)
  except Exception as e:
   print('FAILED',t,e); failed.append({'ticker':t,'error':str(e)})
   if t in old: old[t]['stale']=True; old[t]['update_error']=str(e); stocks.append(old[t])
 if fresh<max(1,int(len(rows)*MIN_SUCCESS_RATIO)): raise RuntimeError('UPDATE REJECTED: insufficient fresh data')
 ihsg={}
 try:
  ih=dl('^JKSE','2y','1d'); x=analyze(ih); market_score=x['score']; ihsg={**x,'ticker':'^JKSE','name':'IHSG / IDX Composite','market_signal':market_score,'signal':('MARKET SUPPORTIVE' if market_score>=70 else 'MARKET CAUTION' if market_score>=50 else 'MARKET RISK'),'updated_at':datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}
 except Exception as e: ihsg={'ticker':'^JKSE','status':'unavailable','error':str(e)}
 stocks.sort(key=lambda x:x.get('professional_score',0),reverse=True)
 data={'schema_version':'3.4','engine':'IDX TERMINAL PRO V3.4 Market + IHSG Engine','last_updated':datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB'),'database_total':len(rows),'success_total':fresh,'failed_total':len(failed),'failed':failed,'ihsg':ihsg,'all_stocks':stocks,'stocks':stocks,'top_10_entry':stocks[:10],'total_emiten':len(stocks)}
 data=clean(data); fd,tmp=tempfile.mkstemp(prefix='data_',suffix='.json'); os.close(fd)
 with open(tmp,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
 os.replace(tmp,OUT_FILE); print('UPDATE OK:',fresh,'/',len(rows),'| IHSG',ihsg.get('close','unavailable'))
if __name__=='__main__': main()
    
