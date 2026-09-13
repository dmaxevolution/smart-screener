#!/usr/bin/env python3
import json, math, os, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yfinance as yf

BASE=os.path.dirname(os.path.abspath(__file__))
EMITEN=os.path.join(BASE,"emiten.json")
DATA=os.path.join(BASE,"data.json")
TMP=DATA+".tmp"

def clean_json(x):
    if isinstance(x,dict): return {str(k):clean_json(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean_json(v) for v in x]
    if isinstance(x,np.integer): return int(x)
    if isinstance(x,(np.floating,float)):
        v=float(x); return None if math.isnan(v) or math.isinf(v) else v
    try:
        if pd.isna(x): return None
    except: pass
    return x

def load(path,default):
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except:return default

def get_df(symbol,period,interval):
    for _ in range(3):
        try:
            df=yf.download(symbol+".JK",period=period,interval=interval,progress=False,auto_adjust=True,threads=False,timeout=20)
            if df is not None and not df.empty:
                if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
                return df
        except: pass
        time.sleep(1)
    return None

def n(v):
    try:
        v=float(v); return None if math.isnan(v) or math.isinf(v) else v
    except:return None

def analyse(meta):
    t=meta["ticker"]
    d=get_df(t,"2y","1d")
    if d is None or len(d)<30: raise RuntimeError("daily data unavailable")
    # SAFE: Yahoo 1h is intentionally limited to 60 days.
    h=get_df(t,"60d","1h")

    c=pd.to_numeric(d["Close"],errors="coerce")
    e20=c.ewm(span=20,adjust=False).mean()
    e50=c.ewm(span=50,adjust=False).mean()
    e200=c.ewm(span=200,adjust=False).mean()
    delta=c.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
    rsi=100-(100/(1+(gain/loss.replace(0,np.nan))))
    macd=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    ms=macd.ewm(span=9,adjust=False).mean()

    score=50
    if c.iloc[-1]>e20.iloc[-1]: score+=10
    else: score-=8
    if e20.iloc[-1]>e50.iloc[-1]: score+=12
    else: score-=10
    if c.iloc[-1]>e200.iloc[-1]: score+=8
    else: score-=7
    if 50<=rsi.iloc[-1]<=70: score+=10
    elif rsi.iloc[-1]<35 or rsi.iloc[-1]>80: score-=8
    if macd.iloc[-1]>ms.iloc[-1]: score+=8
    else: score-=6
    score=max(0,min(100,int(round(score))))

    if score>=85: signal,status="STRONG BUY","ENTRY NOW"
    elif score>=75: signal,status="BUY","READY"
    elif score>=50: signal,status="WAIT","WAIT"
    else: signal,status="AVOID","AVOID"

    prev=n(c.iloc[-2]); close=n(c.iloc[-1])
    return {
      "ticker":t,"symbol":t,"sector":meta.get("sector","Unknown"),
      "close":close,"price":close,"open":n(d["Open"].iloc[-1]),"high":n(d["High"].iloc[-1]),"low":n(d["Low"].iloc[-1]),
      "volume":n(d["Volume"].iloc[-1]) if "Volume" in d else None,
      "change_pct":n((close-prev)/prev*100) if close is not None and prev else None,
      "ema20":n(e20.iloc[-1]),"ema50":n(e50.iloc[-1]),"ema200":n(e200.iloc[-1]),
      "rsi":n(rsi.iloc[-1]),"macd":n(macd.iloc[-1]),"macd_signal":n(ms.iloc[-1]),
      "professional_score":score,"score":score,"entry_probability":score,"signal_strength":score,
      "signal":signal,"entry_status":status,
      "timeframes":{"daily":{"score":score},"1h":{"status":"available" if h is not None else "unavailable"}},
      "updated_at":datetime.now(timezone.utc).isoformat()
    }

def main():
    raw=load(EMITEN,{})
    items=raw.get("emiten",[]) if isinstance(raw,dict) else raw
    emitens=[]
    for x in items:
        if isinstance(x,str): x={"ticker":x}
        if x.get("active",True) and x.get("ticker"):
            x=dict(x); x["ticker"]=str(x["ticker"]).upper().replace(".JK",""); emitens.append(x)
    if not emitens: raise RuntimeError("No active emiten found in emiten.json")

    old=load(DATA,{})
    oldstocks=old.get("all_stocks",old.get("stocks",[])) if isinstance(old,dict) else []
    oldmap={str(s.get("ticker","")).upper().replace(".JK",""):s for s in oldstocks}
    out=[]; failed=[]; fresh=0
    print(f"DATABASE: {len(emitens)} active emiten")

    for i,m in enumerate(emitens,1):
        t=m["ticker"]
        try:
            s=analyse(m); out.append(s); fresh+=1
            print(f"OK {i}/{len(emitens)} {t}")
        except Exception as e:
            print(f"FAILED {t} {e}"); failed.append({"ticker":t,"error":str(e)})
            if t in oldmap:
                s=dict(oldmap[t]); s["stale"]=True; s["update_error"]=str(e); out.append(s)

    if fresh==0: raise RuntimeError("UPDATE REJECTED: no fresh data")
    data={"version":"FINAL ENGINE FIX","generated_at":datetime.now(timezone.utc).isoformat(),
          "total_emiten":len(out),"database_total":len(emitens),"success_total":fresh,
          "failed_total":len(failed),"failed":failed,"all_stocks":out,"stocks":out}
    data=clean_json(data)
    with open(TMP,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
    os.replace(TMP,DATA)
    print(f"UPDATE OK: {fresh}/{len(emitens)} | TOTAL WEB: {len(out)} | FAILED: {len(failed)}")

if __name__=="__main__":
    main()
