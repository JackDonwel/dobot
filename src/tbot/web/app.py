"""TBot Web Dashboard — FastAPI app with embedded HTML UI."""

import logging
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from tbot.core.graph import AgentGraph
from tbot.tools.market import MarketDataProvider

app = FastAPI(title="TBot Dashboard", version="0.2.0")
logger = logging.getLogger("tbot.web")

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBot Dashboard</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px}
  .container{max-width:1200px;margin:0 auto}
  h1{color:#58a6ff;margin-bottom:8px;font-size:24px}
  .subtitle{color:#8b949e;margin-bottom:24px;font-size:14px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:24px}
  .card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}
  .card h3{color:#58a6ff;font-size:14px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px}
  .card .value{font-size:28px;font-weight:600;color:#f0f6fc}
  .card .label{font-size:12px;color:#8b949e;margin-top:4px}
  .card .row{display:flex;justify-content:space-between;padding:4px 0;font-size:13px}
  .card .row .k{color:#8b949e}
  .card .row .v{color:#f0f6fc;font-weight:500}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;padding:8px 12px;border-bottom:2px solid #30363d;color:#8b949e;text-transform:uppercase;font-size:11px;letter-spacing:.5px}
  td{padding:8px 12px;border-bottom:1px solid #21262d}
  .badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
  .badge-win{background:#1b3828;color:#3fb950}
  .badge-loss{background:#3d1f1f;color:#f85149}
  .badge-open{background:#1b2d45;color:#58a6ff}
  .badge-pending{background:#2d281b;color:#d29922}
  .win{color:#3fb950}
  .loss{color:#f85149}
  .neutral{color:#d29922}
  .price-up{color:#3fb950}
  .price-down{color:#f85149}
  button{background:#238636;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500}
  button:hover{background:#2ea043}
  button:disabled{background:#21262d;color:#8b949e;cursor:not-allowed}
  select{background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:8px 12px;font-size:13px;margin-right:8px}
  .actions{display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
  .loading{opacity:.5;pointer-events:none}
  .toast{position:fixed;bottom:24px;right:24px;background:#238636;color:#fff;padding:12px 20px;border-radius:8px;font-size:13px;display:none;z-index:100}
  .toast.error{background:#da3633}
  .tabs{display:flex;gap:0;margin-bottom:16px}
  .tab{padding:8px 20px;cursor:pointer;border:1px solid #30363d;background:#0d1117;color:#8b949e;font-size:13px}
  .tab:first-child{border-radius:6px 0 0 6px}
  .tab:last-child{border-radius:0 6px 6px 0}
  .tab.active{background:#161b22;color:#f0f6fc;border-color:#58a6ff}
  .section{margin-bottom:24px}
  .section h2{color:#f0f6fc;font-size:16px;margin-bottom:12px}
  .price-card{display:flex;justify-content:space-between;align-items:center;padding:12px;background:#0d1117;border-radius:6px;border:1px solid #21262d;margin-bottom:8px}
  .price-card .pair{font-weight:600;color:#f0f6fc;font-size:15px}
  .price-card .price{font-size:18px;font-weight:600}
  .price-card .change{font-size:12px;margin-left:8px}
  .flex-row{display:flex;gap:16px;flex-wrap:wrap}
  .flex-row > *{flex:1;min-width:300px}
  .mt-2{margin-top:8px}
</style>
</head>
<body>
<div class="container">
  <h1>🤖 TBot Dashboard</h1>
  <div class="subtitle">Multi-Agent AI Trading System · <span id="last-updated">—</span></div>

  <div class="grid" id="status-cards"></div>

  <div class="section">
    <h2>Live Prices</h2>
    <div id="price-cards"></div>
  </div>

  <div class="section">
    <div class="flex-row">
      <div>
        <h2>Quick Actions</h2>
        <div class="actions">
          <select id="pair-select">
            <option value="EUR/USD">EUR/USD</option>
            <option value="GBP/USD">GBP/USD</option>
          </select>
          <button id="btn-analyze" onclick="analyzePair()">🔍 Analyze</button>
          <button id="btn-run-session" onclick="runSession()">▶ Run Full Session</button>
        </div>
        <div id="analysis-result" style="margin-top:8px;font-size:13px;color:#8b949e"></div>
      </div>
      <div>
        <h2>News Sentiment</h2>
        <div id="news-card" style="font-size:13px"></div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="tabs">
      <div class="tab active" onclick="switchTab('trades')">Recent Trades</div>
      <div class="tab" onclick="switchTab('lessons')">Lessons</div>
    </div>
    <div id="tab-trades"><table><thead><tr><th>Pair</th><th>Direction</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Outcome</th><th>Date</th></tr></thead><tbody id="trades-body"></tbody></table></div>
    <div id="tab-lessons" style="display:none"><table><thead><tr><th>Pair</th><th>Lesson</th><th>Improvement</th><th>Date</th></tr></thead><tbody id="lessons-body"></tbody></table></div>
  </div>
</div>
<div id="toast" class="toast"></div>

<script>
const BASE = '';
let currentTab = 'trades';

async function fetchJSON(url){const r=await fetch(BASE+url);return r.json()}

function updateTime(){document.getElementById('last-updated').textContent=new Date().toLocaleTimeString()}

function showToast(msg,isError=false){const t=document.getElementById('toast');t.textContent=msg;t.className='toast'+(isError?' error':'');t.style.display='block';setTimeout(()=>t.style.display='none',3000)}

function formatPnL(v){const n=parseFloat(v);if(isNaN(n))return'—';return n>=0?`<span class="win">+$${n.toFixed(2)}</span>`:`<span class="loss">-$${Math.abs(n).toFixed(2)}</span>`}

function formatTime(iso){if(!iso)return'—';const d=new Date(iso);return d.toLocaleDateString()+' '+d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}

async function loadStatus(){
  const s=await fetchJSON('/api/status');
  document.getElementById('status-cards').innerHTML=
    `<div class="card"><h3>LLM Provider</h3><div class="value">${s.llm_provider}</div><div class="label">Model: ${s.ollama_model||s.openai_model||'—'}</div></div>`+
    `<div class="card"><h3>Account</h3><div class="value">$${parseFloat(s.account_balance).toLocaleString()}</div><div class="label">Risk: ${(parseFloat(s.risk_per_trade)*100).toFixed(0)}% · Min R:R 1:${s.min_reward_ratio}</div></div>`+
    `<div class="card"><h3>Trades</h3><div class="value">${s.total_trades}</div><div class="label">Win Rate: ${s.win_rate}% · ${s.wins}W / ${s.losses}L</div></div>`+
    `<div class="card"><h3>Market</h3><div class="value">${s.data_source}</div><div class="label">Pairs: ${(s.major_pairs||[]).join(', ')}</div></div>`
}

async function loadPrices(){
  const p=await fetchJSON('/api/prices');
  const c=document.getElementById('price-cards');
  if(!p||Object.keys(p).length===0){c.innerHTML='<div class="price-card"><span class="pair">No price data available</span></div>';return}
  c.innerHTML=Object.entries(p).map(([pair,data])=>{
    if(!data||data.price===null)return`<div class="price-card"><span class="pair">${pair}</span><span class="neutral">—</span></div>`
    const change=data.change||0
    const cls=change>=0?'price-up':'price-down'
    const sign=change>=0?'+':''
    return`<div class="price-card"><span class="pair">${pair}</span><span><span class="price ${cls}">${parseFloat(data.price).toFixed(5)}</span><span class="change ${cls}">${sign}${change.toFixed(2)}%</span></span></div>`
  }).join('')
}

async function loadTrades(){
  const t=await fetchJSON('/api/trades?limit=20');
  const body=t.map(trade=>`<tr>
    <td>${trade.pair||'—'}</td>
    <td><span class="badge ${trade.direction==='BUY'?'badge-open':'badge-loss'}">${trade.direction||'—'}</span></td>
    <td>${trade.entry_price?parseFloat(trade.entry_price).toFixed(5):'—'}</td>
    <td>${trade.exit_price?parseFloat(trade.exit_price).toFixed(5):'—'}</td>
    <td>${formatPnL(trade.pnl)}</td>
    <td>${trade.outcome?`<span class="badge badge-${trade.outcome==='WIN'?'win':'loss'}">${trade.outcome}</span>`:'<span class="badge badge-open">OPEN</span>'}</td>
    <td>${formatTime(trade.created_at)}</td>
  </tr>`).join('')
  document.getElementById('trades-body').innerHTML=body||'<tr><td colspan="7" style="text-align:center;color:#8b949e">No trades yet</td></tr>'
}

async function loadLessons(){
  const l=await fetchJSON('/api/lessons?limit=10');
  const body=l.map(ls=>`<tr>
    <td>${ls.pair||'—'}</td>
    <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${ls.lesson_text||'—'}</td>
    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${ls.improvement||'—'}</td>
    <td>${formatTime(ls.created_at)}</td>
  </tr>`).join('')
  document.getElementById('lessons-body').innerHTML=body||'<tr><td colspan="4" style="text-align:center;color:#8b949e">No lessons yet</td></tr>'
}

async function loadNews(){
  const n=await fetchJSON('/api/news');
  const c=document.getElementById('news-card');
  if(!n||n.length===0){c.innerHTML='<span class="neutral">No live news available</span>';return}
  c.innerHTML=n.map(a=>`<div style="padding:6px 0;border-bottom:1px solid #21262d">${a.title}<br><span style="font-size:11px;color:#8b949e">${a.source||''} · ${a.published||''}</span></div>`).join('')
}

async function analyzePair(){
  const pair=document.getElementById('pair-select').value
  const btn=document.getElementById('btn-analyze')
  const result=document.getElementById('analysis-result')
  btn.disabled=true;result.textContent='⏳ Analyzing...'
  try{
    const r=await fetchJSON('/api/analyze/'+encodeURIComponent(pair))
    result.innerHTML=r.signal
      ? `<span class="win">✓ Signal: ${r.direction} @ ${r.entry} (conf: ${r.confidence})</span>`
      : `<span class="neutral">No trade signal for ${pair}</span>`
    await Promise.all([loadTrades(),loadLessons(),loadStatus()])
  }catch(e){result.innerHTML=`<span class="loss">✗ Error: ${e.message}</span>`}
  finally{btn.disabled=false}
}

async function runSession(){
  const btn=document.getElementById('btn-run-session')
  const result=document.getElementById('analysis-result')
  btn.disabled=true;result.textContent='⏳ Running full session...'
  try{
    const r=await fetchJSON('/api/session')
    result.innerHTML=`<span class="win">✓ Session complete — ${r.pairs_analyzed} pairs analyzed, ${r.trades_executed} trades</span>`
    await Promise.all([loadTrades(),loadLessons(),loadStatus()])
  }catch(e){result.innerHTML=`<span class="loss">✗ Error: ${e.message}</span>`}
  finally{btn.disabled=false}
}

function switchTab(tab){
  currentTab=tab
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.textContent.trim().toLowerCase().includes(tab)))
  document.getElementById('tab-trades').style.display=tab==='trades'?'block':'none'
  document.getElementById('tab-lessons').style.display=tab==='lessons'?'block':'none'
}

async function refresh(){
  await Promise.all([loadStatus(),loadPrices(),loadTrades(),loadLessons(),loadNews()])
  updateTime()
}

refresh()
setInterval(refresh,30000)
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _DASHBOARD_HTML


def _detect_data_source() -> str:
    from tbot.models.config import settings as s
    if s.data_provider == "synthetic":
        return "synthetic (forced)"
    if s.data_provider == "metaapi" or s.meta_api_token:
        async def _check() -> str:
            try:
                from tbot.tools.metaapi_provider import MetaApiMarketDataProvider
                m = MetaApiMarketDataProvider()
                ok = await m.ensure()
                await m.close()
                return "MetaApi (connected)" if ok else "MetaApi (disconnected)"
            except Exception:
                return "MetaApi (unavailable)"
        try:
            import asyncio
            return asyncio.run(_check())
        except Exception:
            return "MetaApi (error)"
    yf_ok = __import__("importlib").import_module("tbot.tools.market").YFINANCE_AVAILABLE
    return "yfinance (live)" if yf_ok else "synthetic (fallback)"


@app.get("/api/status")
async def api_status():
    try:
        from tbot.memory.store import TradeMemory
        from tbot.models.config import settings
        mem = TradeMemory()
        trades = mem.get_recent_trades(999)
        wins = sum(1 for t in trades if t.get("outcome") == "WIN")
        losses = sum(1 for t in trades if t.get("outcome") == "LOSS")
        total = wins + losses
        win_rate = round(wins / total * 100) if total > 0 else 0
        return {
            "llm_provider": settings.llm_provider,
            "ollama_model": settings.ollama_model,
            "openai_model": settings.openai_model,
            "account_balance": settings.account_balance,
            "risk_per_trade": settings.risk_per_trade,
            "min_reward_ratio": settings.min_reward_ratio,
            "major_pairs": settings.major_pairs,
            "session_start": settings.london_session_start,
            "session_end": settings.london_session_end,
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "data_source": _detect_data_source(),
            "chroma_ready": mem.vector_store._ready if mem.vector_store else False,
        }
    except Exception as exc:
        logger.error("Status error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/trades")
async def api_trades(limit: int = Query(20, ge=1, le=200)):
    try:
        from tbot.memory.store import TradeMemory
        mem = TradeMemory()
        return mem.get_recent_trades(limit)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/lessons")
async def api_lessons(limit: int = Query(10, ge=1, le=100)):
    try:
        from tbot.memory.store import TradeMemory
        mem = TradeMemory()
        raw = mem.get_recent_lessons(limit)
        return [
            {
                "pair": r.get("market_context", "").split()[0] if r.get("market_context") else "—",
                "lesson_text": r.get("lesson_text", "")[:200],
                "improvement": r.get("improvement_suggestion", "")[:200],
                "created_at": r.get("created_at", ""),
            }
            for r in raw
        ]
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/prices")
async def api_prices():
    try:
        from tbot.tools.market import YFINANCE_TICKERS
        provider = MarketDataProvider()
        pairs = list(YFINANCE_TICKERS.keys())
        result: dict[str, Any] = {}
        for pair in pairs:
            price = provider.current_price(pair)
            result[pair] = {"price": price, "change": None}
        return result
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/news")
async def api_news():
    try:
        from tbot.tools.news import fetch_live_news
        return fetch_live_news()
    except Exception:
        return []


@app.post("/api/analyze/{pair}")
async def api_analyze(pair: str):
    try:
        pair = pair.replace("%2F", "/").replace("%2f", "/")
        graph = AgentGraph()
        result = await graph.run(pair)
        sig = result.get("signal")
        if sig:
            return {
                "signal": True,
                "direction": sig.direction.value,
                "entry": round(sig.entry_price, 5),
                "stop": round(sig.stop_loss, 5),
                "take_profit": round(sig.take_profit, 5),
                "confidence": f"{sig.confidence:.0%}",
                "reasoning": sig.reasoning[:200],
            }
        return {"signal": False, "reason": result.get("error", "No trade signal")}
    except Exception as exc:
        logger.error("Analyze error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/session")
async def api_session():
    try:
        from tbot.main import run_session
        await run_session()
        return {"status": "ok", "message": "Session complete"}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
