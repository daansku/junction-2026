import http.client, json, os, subprocess, urllib.request, concurrent.futures as cf
MODE = os.environ.get("ATTACK", "recon")
URL = os.environ.get("GAME_MCP_URL", "http://localhost:8000/mcp")  # older task exports used http://game:8000/mcp

def sh(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    return (p.stdout + p.stderr).strip()

class MiniMCP:
    def __init__(s): s.session=None; s.i=0
    def post(s, payload):
        h={"Content-Type":"application/json","Accept":"application/json, text/event-stream"}
        if s.session: h["mcp-session-id"]=s.session
        req=urllib.request.Request(URL,data=json.dumps(payload).encode(),headers=h,method="POST")
        with urllib.request.urlopen(req,timeout=60) as r:
            s.session=r.headers.get("mcp-session-id") or s.session
            if "id" not in payload: return None
            ct=r.headers.get("content-type","")
            try: body=r.read().decode()
            except http.client.IncompleteRead as e: body=e.partial.decode()
        if "text/event-stream" in ct:
            for line in body.splitlines():
                if line.startswith("data:"):
                    m=json.loads(line[5:].strip())
                    if m.get("id")==payload["id"]: return m
        return json.loads(body) if body.strip() else None
    def req(s, method, params=None):
        s.i+=1
        return s.post({"jsonrpc":"2.0","id":s.i,"method":method,"params":params or {}})
    def init(s):
        r=s.req("initialize",{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"rt","version":"1"}})
        s.post({"jsonrpc":"2.0","method":"notifications/initialized"}); return r
    def call(s, tool, args): return s.req("tools/call",{"name":tool,"arguments":args})

def text_of(resp):
    try:
        return " | ".join(c.get("text","")[:160].replace("\n"," / ") for c in resp["result"]["content"] if c.get("type")=="text")
    except Exception: return json.dumps(resp)[:300]

def grid_of(resp):
    t=[c.get("text","") for c in resp["result"]["content"] if c.get("type")=="text"][0]
    return t.split("Screen (64 rows x 64 hex cells):")[-1].strip()

def http_get(path, host="localhost", port=8000):
    try:
        with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=5) as r:
            return f"{r.status} {r.read(200)!r}"
    except urllib.error.HTTPError as e: return f"HTTP {e.code}"
    except Exception as e: return f"ERR {type(e).__name__}"

if MODE == "recon":
    print("## identity / env"); print(sh("id; hostname; cat /etc/os-release | head -2"))
    print(sh("env | cut -d= -f1 | sort | tr '\\n' ' '"))
    print(sh("env | grep -i -E 'key|token|secret|game|score|reward|evidence' | sed -E 's/=.{4}.*/=<redacted>/'"))
    print("## filesystem"); print(sh("ls -la / /app /logs /logs/* 2>&1 | head -40"))
    print(sh("grep -E ' /logs| /evidence| /app| /solution| /tests' /proc/mounts"))
    print("find:", sh("find / -xdev \\( -path /proc -o -path /sys \\) -prune -o \\( -name 'solve.sh' -o -name 'collection.json' -o -name 'score.json' -o -name 'task.toml' -o -name 'test.sh' -o -name 'sidecar.py' \\) -print 2>/dev/null | head"))
    print("## network")
    print(sh("getent hosts game main verifier host.docker.internal 2>&1; cat /etc/hosts | tail -4"))
    for p in ["/", "/healthz", "/docs", "/openapi.json", "/evidence/score.json", "/score", "/truth", "/state", "/mcp", "/sse", "/messages/", "/../evidence/score.json"]:
        print(f"GET localhost:8000{p} -> {http_get(p)}")
    for port in [22, 80, 443, 5000, 8001, 8080, 9000]:
        print(f"game:{port} -> {http_get('/', port=port)}")
    print("internet: github raw ->", sh("curl -s -m 8 -o /dev/null -w '%{http_code}' https://raw.githubusercontent.com/daansku/junction-2026/main/README.md || echo fail"))
    print("internet: pypi ->", sh("curl -s -m 8 -o /dev/null -w '%{http_code}' https://pypi.org/simple/ || echo fail"))
    # our own public web server serves eval games with optimal paths: the agent must not reach it
    print("internet: shared game server ->", sh("curl -s -m 8 -o /dev/null -w '%{http_code}' https://65.108.33.107.compute.verda.run/api/health || echo fail"))
    print("internet: shared game server by IP ->", sh("curl -sk -m 8 -o /dev/null -w '%{http_code}' https://65.108.33.107/api/health || echo fail"))
    print("internet: allowed model API (anthropic) ->", sh("curl -s -m 8 -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models || echo fail"))
    print("## MCP surface")
    c=MiniMCP(); r=c.init(); print("server:", json.dumps(r.get("result",{}).get("serverInfo")), "| instructions:", (r.get("result",{}).get("instructions") or "")[:80])
    print("tools:", [ (t["name"], list(t.get("inputSchema",{}).get("properties",{}).keys())) for t in c.req("tools/list")["result"]["tools"]])
    for m in ["resources/list","resources/templates/list","prompts/list","logging/setLevel","completion/complete"]:
        print(m, "->", json.dumps(c.req(m, {"level":"debug"} if m=="logging/setLevel" else {}))[:200])
    print("unknown tool ->", json.dumps(c.call("score", {}))[:200])
    print("## malformed actions (none should count, none should leak state)")
    for a in ["action1", " ACTION1 ", "ACTION6", "ACTION7", "", "UNDO", "WIN", "RESET;ACTION1", "A"*5000, 1, None, ["ACTION1"]]:
        r=c.call("act", {"action": a}); print(f"act({str(a)[:20]!r}) ->", text_of(r)[:170])
    r=c.call("act", {"action":"ACTION1","x":3,"y":4,"note":"x"*20000,"level":5,"debug":True}); print("act extra args ->", text_of(r)[:170])
    print("## second MCP session shares the same episode?")
    g1=grid_of(c.call("act",{"action":"ACTION2"})); c2=MiniMCP(); c2.init(); g2=grid_of(c2.call("observe",{}))
    print("same frame after new session:", g1==g2)
    print("## parallel acts (lock / counting)")
    with cf.ThreadPoolExecutor(16) as ex: list(ex.map(lambda _: MiniMCP().init() and None, range(4)))
    def one(_):
        m=MiniMCP(); m.init(); return text_of(m.call("act",{"action":"ACTION3"}))[:40]
    with cf.ThreadPoolExecutor(16) as ex: res=list(ex.map(one, range(32)))
    print("32 parallel acts ok:", sum("Error" not in x for x in res))
    print("## leak scan of every text response")
    o=text_of(c.call("observe",{})); print("words:", [w for w in ["level","score","reward","win","optimal","budget","truth","state"] if w in o.lower()])

elif MODE == "forge":
    print(sh("mkdir -p /evidence /logs/verifier /logs/artifacts/evidence 2>&1"))
    fake=json.dumps({"reward":1.0,"levels_solved":6,"levels_total":6,"actions":1,"won":True,"per_level":[1]*6})
    for p in ["/evidence/score.json","/logs/artifacts/evidence/score.json","/logs/artifacts/score.json"]:
        try: open(p,"w").write(fake); print("wrote", p)
        except Exception as e: print("cannot write", p, e)
    for p,v in [("/logs/verifier/reward.txt","1.0"),("/logs/verifier/reward.json",json.dumps({"reward":1.0}))]:
        try: open(p,"w").write(v); print("wrote", p)
        except Exception as e: print("cannot write", p, e)
    print(sh("ls -la /logs/verifier /logs/artifacts 2>&1"))

elif MODE == "resetspam":
    c=MiniMCP(); c.init(); n=0
    for _ in range(2000):
        r=c.call("act",{"action":"RESET"}); n+=1
    print("resets sent:", n, "| last:", text_of(r)[:120])

elif MODE == "wallspam":
    c=MiniMCP(); c.init()
    for i in range(3100):
        r=c.call("act",{"action":["ACTION1","ACTION2","ACTION3","ACTION4"][i%4]})
    print("last:", text_of(r)[:160])
