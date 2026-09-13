import json, math, os
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS = [x.strip() for x in os.getenv('TICKERS','BBCA,BBRI,BMRI,TLKM,ASII,AMMN,MDKA,ANTM,ADRO,ITMG,HRUM,PGAS,ICBP,INDF,UNTR,ERAA,MIKA').split(',')]
SECTOR = {}
INTERVALS = {'1h':('60m','60d'),'4h':('1h','730d'),'daily':('1d','2y'),'weekly':('1wk','5y'),'monthly':('1mo','10y')}

def ema(s,n): return s.ewm(span=n, adjust=False).mean()
def rsi(s,n=14):
    d=s.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean();
    return 100-(100/(1+up/dn.replace(0,np.nan)))
def atr(df,n=14):
    pc=df.Close.shift(); tr=pd.concat([df.High-df.Low,(df.High-pc).abs(),(df.Low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()
def macd(s):
    m=ema(s,12)-ema(s,26); sig=ema(m,9); return m,sig,m-sig
def adx(df,n=14):
    up=df.High.diff(); dn=-df.Low.diff(); plus=up.where((up>dn)&(up>0),0); minus=dn.where((dn>up)&(dn>0),0)
    tr=atr(df,n); p=100*plus.ewm(alpha=1/n,adjust=False).mean()/tr; m=100*minus.ewm(alpha=1/n,adjust=False).mean()/tr
    dx=100*(p-m).abs()/(p+m).replace(0,np.nan); return dx.ewm(alpha=1/n,adjust=False).mean(),p,m
def regime(x):
    if x['close']>x['ema20']>x['ema50']>x['ema200'] and x['adx']>=20:return 'BULLISH'
    if x['close']<x['ema20']<x['ema50']<x['ema200'] and x['adx']>=20:return 'BEARISH'
    return 'SIDEWAYS'
def analyze(df):
    df=df.dropna().copy(); c=df.Close
    if len(df)<210: raise ValueError('insufficient history')
    e20,e50,e200=ema(c,20),ema(c,50),ema(c,200); rr=rsi(c); a=atr(df); ad,pdi,mdi=adx(df); m,ms,mh=macd(c)
    q=df.iloc[-1]; prev=df.iloc[-2]; vol=float(q.Volume or 0); av=float(df.Volume.rolling(20).mean().iloc[-1] or 0); rvol=vol/av if av else 0
    support=float(df.Low.tail(20).min()); resistance=float(df.High.tail(20).max());
    x={'close':float(q.Close),'ema20':float(e20.iloc[-1]),'ema50':float(e50.iloc[-1]),'ema200':float(e200.iloc[-1]),'rsi':float(rr.iloc[-1]),'atr':float(a.iloc[-1]),'adx':float(ad.iloc[-1]),'plus_di':float(pdi.iloc[-1]),'minus_di':float(mdi.iloc[-1]),'macd':float(m.iloc[-1]),'macd_signal':float(ms.iloc[-1]),'macd_hist':float(mh.iloc[-1]),'volume':vol,'avg_volume20':av,'rvol':round(rvol,2),'support':support,'resistance':resistance}
    x['regime']=regime(x); x['macd_bullish']=x['macd']>x['macd_signal']; x['trend_score']=25 if x['regime']=='BULLISH' else (8 if x['regime']=='SIDEWAYS' else 0)
    x['momentum_score']=min(20, max(0, 8+(x['rsi']-50)/2 + (6 if x['macd_bullish'] else 0)))
    x['volume_score']=15 if x['rvol']>=1.5 else (10 if x['rvol']>=1 else 5)
    x['technical_score']=15 if x['adx']>=20 and x['plus_di']>x['minus_di'] else 7
    risk=max(x['atr']*1.5, x['close']*0.015); sl=max(support, x['close']-risk); tp1=x['close']+(x['close']-sl)*2; tp2=x['close']+(x['close']-sl)*3
    x['stop_loss']=round(sl,2); x['take_profit_1']=round(tp1,2); x['take_profit_2']=round(tp2,2); x['rrr']=round((tp1-x['close'])/max(x['close']-sl,0.01),2); x['risk_score']=15 if x['rrr']>=2 else 8
    return x
def strategy(tfs):
    w=tfs.get('weekly',{}); d=tfs.get('daily',{}); h=tfs.get('4h',{}); score=sum([d.get('trend_score',0),d.get('momentum_score',0),d.get('volume_score',0),d.get('technical_score',0),d.get('risk_score',0)])
    align=sum(x.get('regime')=='BULLISH' for x in [w,d,h]); score=min(100,round(score+align*5,1))
    if align>=2 and d.get('close',0)>d.get('resistance',float('inf'))*0.99 and d.get('rvol',0)>=1.2: name='BREAKOUT'
    elif align>=2 and d.get('close',0)<=d.get('ema20',0)*1.03 and d.get('close',0)>=d.get('ema50',0)*0.97: name='PULLBACK'
    elif align>=2: name='TREND FOLLOWING'
    else: name='WAIT / NO TRADE'
    signal='ELITE BUY' if score>=90 else 'STRONG BUY' if score>=80 else 'BUY' if score>=70 else 'WATCHLIST' if score>=60 else 'WAIT' if score>=50 else 'AVOID'
    return score,signal,name,align
def get(ticker):
    out={}
    for key,(iv,period) in INTERVALS.items():
        try:
            df=yf.download(ticker+'.JK',interval=iv,period=period,auto_adjust=True,progress=False,threads=False)
            if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
            out[key]=analyze(df)
        except Exception as e: out[key]={'error':str(e)}
    score,signal,name,align=strategy(out); d=out.get('daily',{})
    return {'ticker':ticker,'sector':SECTOR.get(ticker,'IDX'),'timeframes':out,'professional_score':score,'signal':signal,'strategy':name,'mtf_alignment':align,'close':d.get('close',0),'change_pct':0,'stop_loss':d.get('stop_loss',0),'take_profit_1':d.get('take_profit_1',0),'take_profit_2':d.get('take_profit_2',0)}
def main():
    stocks=[]
    for t in TICKERS:
        try: stocks.append(get(t))
        except Exception as e: print(t,e)
    stocks.sort(key=lambda x:x['professional_score'],reverse=True)
    data={'schema_version':'2.0','engine':'IDX TERMINAL PRO Multi-Timeframe Strategy Engine','last_updated':datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB'),'disclaimer':'Educational screener only. Validate with backtest and risk management.','timeframes':list(INTERVALS),'all_stocks':stocks,'top_10_entry':stocks[:10],'total_emiten':len(stocks)}
    with open('data.json','w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__': main()
