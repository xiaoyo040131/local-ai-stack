# -*- coding: utf-8 -*-
"""
local-ai-stack: Anthropic / OpenAI compatible proxy for local Ollama models.

What it does
------------
- Receives Anthropic /v1/messages requests (used by Claude Code) and forwards
  them to Ollama's native /api/chat endpoint.
- Also speaks OpenAI /v1/chat/completions.
- Bridges tool calls so a local model can use Claude Code's web_search tool
  (model decides -> Claude Code executes the search -> result is fed back
  to the model for a final answer).
- Fixes a common problem: reasoning models like gpt-oss return an empty
  `content` through Ollama's OpenAI/Anthropic compatible endpoints (the answer
  is swallowed into `thinking`). Ollama's native /api/chat returns `content`
  correctly, so we route through it.

Usage
-----
    python gptoss_proxy.py

Environment variables (all optional)
    OLLAMA_API   - Ollama chat endpoint, default http://localhost:11434/api/chat
    OLLAMA_MODEL - model name, default gpt-oss:20b
    PROXY_PORT   - listen port, default 11435

Then point a client at http://localhost:11435, e.g. for Claude Code set:
    ANTHROPIC_BASE_URL=http://localhost:11435
    ANTHROPIC_AUTH_TOKEN=ollama
    ANTHROPIC_MODEL=<your model>
"""
import json, os, urllib.request, time, uuid, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

OLLAMA_API = os.environ.get("OLLAMA_API", "http://localhost:11434/api/chat")
MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
PORT = int(os.environ.get("PROXY_PORT", "11435"))

# Web-search tools we expose to the model (Claude Code's built-in web_search).
# Key logic: once the message history already contains a tool_result (i.e. a
# search has already happened), we stop passing tools to the model so it is
# forced to summarise — this avoids an infinite search loop.
WEB_TOOLS = {"WebSearch", "web_search"}


def make_tool_id():
    return "toolu_" + uuid.uuid4().hex[:12]


def make_msg_id():
    return "msg_" + uuid.uuid4().hex[:24]


def tools_anthropic_to_ollama(tools):
    """Convert Anthropic tools -> Ollama(OpenAI) tools, keeping only web tools."""
    if not tools:
        return []
    out = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        name = t.get("name")
        if name not in WEB_TOOLS:
            continue
        fn = {"name": name,
              "description": t.get("description", ""),
              "parameters": t.get("input_schema", {"type": "object", "properties": {}})}
        out.append({"type": "function", "function": fn})
    return out


def messages_anthropic_to_ollama(messages):
    """Anthropic message list -> Ollama message list (tool_result -> tool msg)."""
    oms = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str):
            oms.append({"role": role, "content": content})
            continue
        blocks = content if isinstance(content, list) else []
        if role == "assistant":
            text = "".join(b.get("text", "") for b in blocks
                           if isinstance(b, dict) and b.get("type") == "text")
            tool_calls = []
            for b in blocks:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tool_calls.append({
                        "type": "function",
                        "function": {"name": b.get("name", ""),
                                     "arguments": b.get("input", {})}
                    })
            if tool_calls:
                oms.append({"role": "assistant", "content": text, "tool_calls": tool_calls})
            else:
                oms.append({"role": "assistant", "content": text})
        elif role == "user":
            text_parts = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "tool_result":
                    tc = b.get("content")
                    if isinstance(tc, list):
                        tc = "".join(x.get("text", "") for x in tc if isinstance(x, dict))
                    oms.append({"role": "tool", "content": "" if tc is None else str(tc)})
                elif bt == "text":
                    text_parts.append(b.get("text", ""))
            if text_parts:
                oms.append({"role": "user", "content": "\n".join(text_parts)})
    return oms


def to_ollama_body(messages, model, max_tokens=None, temperature=None, top_p=None, system=None, tools=None):
    o = {"model": model, "stream": False}
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs += messages
    o["messages"] = msgs
    if tools:
        o["tools"] = tools
    opts = {}
    if max_tokens:
        opts["num_predict"] = int(max_tokens)
    if temperature is not None:
        opts["temperature"] = temperature
    if top_p is not None:
        opts["top_p"] = top_p
    if opts:
        o["options"] = opts
    return o


def call_ollama(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def ollama_message_to_anthropic_blocks(msg, model):
    """Ollama assistant message -> Anthropic content blocks (text + tool_use)."""
    text = msg.get("content", "")
    blocks = []
    if text:
        blocks.append({"type": "text", "text": text})
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                inp = json.loads(args)
            except Exception:
                inp = {}
        else:
            inp = args or {}
        blocks.append({"type": "tool_use", "id": make_tool_id(),
                       "name": fn.get("name", ""), "input": inp})
    return blocks


def stop_reason_for(blocks):
    return "tool_use" if any(b.get("type") == "tool_use" for b in blocks) else "end_turn"


# ---------- Anthropic /v1/messages ----------
def handle_anthropic(handler, body):
    model = body.get("model", MODEL)
    stream = body.get("stream", False)
    max_tokens = body.get("max_tokens")
    messages = body.get("messages", [])
    system = body.get("system", "")
    if isinstance(system, list):
        system = "".join(b.get("text", "") for b in system if b.get("type") == "text")
    tools_raw = body.get("tools", [])
    # If history already contains a tool_result (already searched), stop passing
    # tools so the model is forced to summarise and the loop breaks.
    has_prev_tool = any(isinstance(m.get("content"), list) and
                        any(isinstance(b, dict) and b.get("type") == "tool_result"
                            for b in m.get("content"))
                        for m in messages if isinstance(m, dict))
    tools = [] if has_prev_tool else tools_anthropic_to_ollama(tools_raw)
    oms = messages_anthropic_to_ollama(messages)
    o = to_ollama_body(oms, model, max_tokens, body.get("temperature"), body.get("top_p"),
                       system, tools)
    try:
        raw = call_ollama(o)
    except Exception as e:
        handler.send_response(502)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"type": "error", "error": {"type": "api_error", "message": str(e)}}).encode())
        return

    r = json.loads(raw.decode("utf-8"))
    blocks = ollama_message_to_anthropic_blocks(r.get("message", {}), model)
    usage_in = r.get("prompt_eval_count", 0)
    usage_out = r.get("eval_count", 0)

    if not stream:
        msg = {"id": make_msg_id(), "type": "message", "role": "assistant", "model": model,
               "content": blocks, "stop_reason": stop_reason_for(blocks),
               "usage": {"input_tokens": usage_in, "output_tokens": usage_out}}
        out = json.dumps(msg).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(out)))
        handler.end_headers()
        handler.wfile.write(out)
    else:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        mid = make_msg_id()
        handler.sse("message_start", {"type": "message_start",
            "message": {"id": mid, "type": "message", "role": "assistant", "model": model,
                        "content": [], "usage": {"input_tokens": usage_in, "output_tokens": usage_out}}})
        for idx, block in enumerate(blocks):
            handler.sse("content_block_start", {"type": "content_block_start", "index": idx,
                "content_block": block})
            if block["type"] == "text":
                handler.sse("content_block_delta", {"type": "content_block_delta", "index": idx,
                    "delta": {"type": "text_delta", "text": block["text"]}})
            else:  # tool_use
                handler.sse("content_block_delta", {"type": "content_block_delta", "index": idx,
                    "delta": {"type": "input_json_delta", "partial_json": json.dumps(block.get("input", {}), ensure_ascii=False)}})
            handler.sse("content_block_stop", {"type": "content_block_stop", "index": idx})
        handler.sse("message_delta", {"type": "message_delta",
            "delta": {"stop_reason": stop_reason_for(blocks)},
            "usage": {"input_tokens": usage_in, "output_tokens": usage_out}})
        handler.sse("message_stop", {"type": "message_stop"})
        handler.wfile.write(b"\n")
        handler.wfile.flush()


# ---------- OpenAI /v1/chat/completions ----------
def handle_openai(handler, body):
    model = body.get("model", MODEL)
    stream = body.get("stream", False)
    o = to_ollama_body(body.get("messages", []), model, body.get("max_tokens"),
                       body.get("temperature"), body.get("top_p"))
    try:
        raw = call_ollama(o)
    except Exception as e:
        handler.send_response(502)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": {"message": str(e)}}).encode())
        return
    if not stream:
        r = json.loads(raw.decode("utf-8"))
        text = r.get("message", {}).get("content", "")
        out = json.dumps({
            "id": "chatcmpl-proxy", "object": "chat.completion", "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": r.get("prompt_eval_count", 0),
                      "completion_tokens": r.get("eval_count", 0)}
        }).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(out)))
        handler.end_headers()
        handler.wfile.write(out)
    else:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        for raw_line in raw.decode("utf-8", "ignore").split("\n"):
            line = raw_line.strip()
            if not line.startswith("{"):
                continue
            try:
                chunk = json.loads(line)
            except Exception:
                continue
            if chunk.get("done"):
                d = {"id": "chatcmpl-proxy", "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": chunk.get("prompt_eval_count", 0),
                               "completion_tokens": chunk.get("eval_count", 0)}}
                handler.wfile.write(b"data: " + json.dumps(d).encode() + b"\n\n")
                handler.wfile.write(b"data: [DONE]\n\n")
                handler.wfile.flush()
                break
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                d = {"id": "chatcmpl-proxy", "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": model, "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]}
                handler.wfile.write(b"data: " + json.dumps(d).encode() + b"\n\n")
                handler.wfile.flush()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def sse(self, event, data):
        self.wfile.write(("event: %s\ndata: %s\n\n" % (event, json.dumps(data, ensure_ascii=False))).encode("utf-8"))
        self.wfile.flush()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self.send_error(400)
            return
        path = urlparse(self.path).path.rstrip("/")
        if path.endswith("/v1/messages"):
            handle_anthropic(self, body)
        elif path.endswith("/v1/chat/completions"):
            handle_openai(self, body)
        else:
            self.send_error(404)

    def do_GET(self):
        if urlparse(self.path).path.rstrip("/").endswith("/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(404)


if __name__ == "__main__":
    print(f"local-ai-stack proxy listening on {PORT} (model={MODEL})")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.serve_forever()
