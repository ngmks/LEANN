import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "apps"))
from slack_data.slack_mcp_reader import SlackMCPReader


async def fetch(
    channel_id: str | None,
    channel_name: str | None,
    workspace_name: str | None,
    query: str,
    search: str | None,
):
    reader = SlackMCPReader(
        mcp_server_command="slack-mcp-server",
        workspace_name=workspace_name,
        concatenate_conversations=True,
        max_messages_per_conversation=10000000000,
        max_retries=5,
        retry_delay=2.0,
    )
    async with reader:
        print("Connected to Slack MCP server!")
        if channel_name and not channel_id:
            lst = await reader.send_mcp_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "channels_list", "arguments": {}},
                }
            )
            text = lst.get("result", {}).get("content", [{"text": ""}])[0]["text"]
            for line in text.splitlines()[1:]:
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2:
                    continue
                cid, name = parts[0], parts[1].lstrip("#")
                if name.lower() == channel_name.lower():
                    channel_id = cid
                    print(f"Resolved channel name #{channel_name} -> {channel_id}")
                    break
            if not channel_id:
                print(f"No channel named '{channel_name}' found.")
                return
        if not channel_id:
            print("Provide --channel-id or --channel-name.")
            return

        # If search is provided, try to use a search tool first
        resp = None
        if search:
            try:
                tools = await reader.list_available_tools()
                search_tool = None
                for t in tools:
                    name = t.get("name", "").lower()
                    if "search" in name and "message" in name:
                        search_tool = t["name"]
                        break
                if search_tool:
                    print(f"Searching with tool '{search_tool}' for: {search}")
                    resp = await reader.send_mcp_request(
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/call",
                            "params": {
                                "name": search_tool,
                                "arguments": {
                                    "query": search,
                                    "channel_id": channel_id,
                                    "limit": 200,
                                },
                            },
                        }
                    )
                else:
                    print("Search tool not available, falling back to full history.")
            except Exception as e:
                print(f"Search failed ({e}), falling back to full history.")

        if resp is None:
            print(f"Fetching messages from {channel_id} ...")
            resp = await reader.send_mcp_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "conversations_history",
                        "arguments": {"channel_id": channel_id, "limit": 10000000000},
                    },
                }
            )
        if "error" in resp:
            msg = resp["error"].get("message", "Unknown")
            print("Error:", msg)
            if msg in ("not_in_channel", "channel_not_found"):
                print("Tip: invite the bot to the channel: /invite @YourBotName")
            return
        result = resp.get("result", {})
        content = result.get("content")
        text_blob = None
        if isinstance(content, list) and content and "text" in content[0]:
            text_blob = content[0]["text"]
            print(text_blob[:4000])
        else:
            print(result)

        # Simple RAG-style answer with LEANN-focused boosting
        if query and text_blob:
            print("\n" + "=" * 60)
            print("RAG ANSWER")
            print("=" * 60)
            q_terms = [t.strip().lower() for t in query.split() if t.strip()]
            lines = [
                l
                for l in (text_blob.splitlines() if text_blob else [])
                if l and not l.startswith("MsgID,")
            ]
            # Score lines by count of query terms present
            scored = []
            boost_terms = {
                "leann": 5,
                "yichuan-w/leann": 4,
                "github.com/yichuan-w/leann": 4,
                "x.com/yichuanm": 3,
                "leann vector": 3,
            }
            for ln in lines:
                ll = ln.lower()
                score = sum(1 for t in q_terms if t in ll)
                for k, b in boost_terms.items():
                    if k in ll:
                        score += b
                if score > 0:
                    scored.append((score, ln))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = [ln for _, ln in scored[:5]]
            if top:
                print(f"Query: {query}")
                print("Relevant messages:")
                for i, ln in enumerate(top, 1):
                    print(f"  {i}. {ln}")
                leann_hits = [ln for ln in lines if "leann" in ln.lower()][:5]
                if leann_hits:
                    print("\nLEANN-focused highlights:")
                    for i, ln in enumerate(leann_hits, 1):
                        print(f"  {i}. {ln}")
            else:
                print(f"Query: {query}")
                print("No directly matching messages found; showing recent context:")
                for i, ln in enumerate(lines[:5], 1):
                    print(f"  {i}. {ln}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel-id", default=None)
    ap.add_argument("--channel-name", default=None, help="e.g., random")
    ap.add_argument("--workspace-name", default="Sky Lab Computing")
    ap.add_argument("--query", default="What is LEANN about?", help="Simple RAG-style query")
    ap.add_argument("--search", default=None, help="Server-side message search query")
    args = ap.parse_args()
    asyncio.run(
        fetch(
            args.channel_id,
            args.channel_name,
            args.workspace_name,
            args.query,
            args.search,
        )
    )


if __name__ == "__main__":
    main()
