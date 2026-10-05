# -*- coding: utf-8 -*-
"""
local-ai-stack: terminal chat tool with live web search.

Talk to your local Ollama model in a command line. The model can call a
`web_search` tool, which this script executes against Bing (fallback Baidu),
then the model summarises the results in Chinese.

Usage
-----
    python webchat.py
    or double-click webchat.bat

Environment variables (optional)
    OLLAMA_API   - Ollama chat endpoint, default http://localhost:11434/api/chat
    OLLAMA_MODEL - model name, default gpt-oss:20b

Type `exit` / `quit` to leave.
"""
import json, os, urllib.request, urllib.parse, re, sys

# Make Chinese display correctly in the Windows terminal (used with chcp 65001).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
API = os.environ.get("OLLAMA_API", "http://localhost:11434/api/chat")

# ---------- Web search (Bing primary, Baidu fallback) ----------
def _fetch(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")


def _parse_bing(html, n=5):
    results = []
    blocks = re.findall(r'<li class="b_algo".*?</li>', html, re.S)
    for b in blocks[:n]:
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not m:
            continue
        link, title = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
        s = re.search(r'<p[^>]*>(.*?)</p>', b, re.S)
        snippet = re.sub(r'<[^>]+>', '', s.group(1)).strip() if s else ""
        results.append({"title": title, "link": link, "snippet": snippet})
    return results


def _parse_baidu(html, n=5):
    results = []
    blocks = re.findall(r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>.*?</h3>', html, re.S)
    for b in blocks[:n]:
        m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not m:
            continue
        link, title = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
        results.append({"title": title, "link": link, "snippet": ""})
    return results


def web_search(query, n=5):
    n = int(n)
    errs = []
    try:
        html = _fetch("https://cn.bing.com/search?q=" + urllib.parse.quote(query))
        res = _parse_bing(html, n)
        if res:
            return json.dumps({"results": res}, ensure_ascii=False)
        errs.append("bing no results")
    except Exception as e:
        errs.append(f"bing failed:{e}")
    try:
        html = _fetch("https://www.baidu.com/s?wd=" + urllib.parse.quote(query))
        res = _parse_baidu(html, n)
        if res:
            return json.dumps({"results": res}, ensure_ascii=False)
        errs.append("baidu no results")
    except Exception as e:
        errs.append(f"baidu failed:{e}")
    return json.dumps({"error": "search failed", "detail": ";".join(errs)}, ensure_ascii=False)


TOOLS = [{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the internet for latest/real-time information. Use when the user asks about news, "
                       "hot topics, facts, or anything you don't know.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "search keywords"}},
            "required": ["query"]
        }
    }
}]


# ---------- Call the model ----------
def call_model(messages, use_tools=True):
    payload = {"model": MODEL, "messages": messages, "stream": False}
    if use_tools:
        payload["tools"] = TOOLS
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8")).get("message", {})


def run_tool(name, args):
    if name == "web_search":
        print("  [searching] " + args.get("query", ""))
        return web_search(args.get("query", ""))
    return json.dumps({"error": f"unknown tool {name}"})


# ---------- Main loop ----------
def main():
    print("=" * 52)
    print("  Terminal Chat (with web search)  |  model: %s" % MODEL)
    print("  The model can search the web automatically. Type exit to quit.")
    print("=" * 52)
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception:
        print("[error] Cannot reach Ollama. Start Ollama first, then run this tool.")
        input("Press Enter to exit...")
        return

    messages = [{"role": "system", "content":
                 "You are an assistant that can search the web. When the user needs real-time or unknown "
                 "information, call the web_search tool. After searching, summarise the results in concise Chinese. "
                 "Generally search 1-2 times; do not repeatedly search the same question or add unnecessary searches."}]
    while True:
        try:
            q = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break
        messages.append({"role": "user", "content": q})
        for _ in range(3):
            try:
                msg = call_model(messages, use_tools=True)
            except Exception as e:
                print(f"[error] model call failed: {e}")
                break
            if "tool_calls" in msg and msg["tool_calls"]:
                messages.append(msg)
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {"query": args}
                    result = run_tool(fn.get("name", ""), args)
                    messages.append({"role": "tool", "content": result})
            else:
                print("\nModel: " + (msg.get("content", "") or "").strip())
                messages.append(msg)
                break
        else:
            # After 3 rounds the model is still searching; force it to summarise.
            print("  (information collected, generating answer...)")
            results = "\n".join(m.get("content", "") for m in messages if m.get("role") == "tool")
            forced = [
                {"role": "system", "content": "You are a Chinese assistant. Answer the user's question based "
                                              "on the provided information."},
                {"role": "user", "content": f"User question: {q}\n\nSearch results:\n{results}\n\n"
                                            "Please answer concisely in Chinese based on the search results. "
                                            "Do not mention the search process."}
            ]
            try:
                msg = call_model(forced, use_tools=False)
                print("\nModel: " + (msg.get("content", "") or "").strip())
                messages.append({"role": "assistant", "content": msg.get("content", "") or ""})
            except Exception as e:
                print(f"[error] {e}")


if __name__ == "__main__":
    main()
