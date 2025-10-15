# Slack Integration Setup Guide

This guide provides step-by-step instructions for setting up Slack integration with LEANN.

## Overview

LEANN's Slack integration uses MCP (Model Context Protocol) servers to fetch and index your Slack messages for RAG (Retrieval-Augmented Generation). This allows you to search through your Slack conversations using natural language queries.

## Prerequisites

1. **Slack Workspace Access**: You need admin or owner permissions in your Slack workspace to create apps and configure OAuth tokens.

2. **Slack MCP Server**: Install a Slack MCP server (e.g., `slack-mcp-server` via npm)

3. **LEANN**: Ensure you have LEANN installed and working

## Step 1: Create a Slack App

### 1.1 Go to Slack API Dashboard

1. Visit [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter your app name (e.g., "LEANN Slack Integration")
5. Select your workspace
6. Click **"Create App"**

### 1.2 Configure App Permissions

#### Bot Token Scopes

1. In your app dashboard, go to **"OAuth & Permissions"** in the left sidebar
2. Scroll down to **"Scopes"** section
3. Under **"Bot Token Scopes"**, click **"Add an OAuth Scope"**
4. Add the following scopes:
   - `channels:read` - Read public channel information
   - `channels:history` - Read messages in public channels
   - `groups:read` - Read private channel information
   - `groups:history` - Read messages in private channels
   - `im:read` - Read direct message information
   - `im:history` - Read direct messages
   - `mpim:read` - Read group direct message information
   - `mpim:history` - Read group direct messages
   - `users:read` - Read user information
   - `team:read` - Read workspace information

#### App-Level Tokens (Optional)

Some MCP servers may require app-level tokens:

1. Go to **"Basic Information"** in the left sidebar
2. Scroll down to **"App-Level Tokens"**
3. Click **"Generate Token and Scopes"**
4. Enter a name (e.g., "LEANN Integration")
5. Add the `connections:write` scope
6. Click **"Generate"**
7. Copy the token (starts with `xapp-`)

### 1.3 Install App to Workspace

1. Go to **"OAuth & Permissions"** in the left sidebar
2. Click **"Install to Workspace"**
3. Review the permissions and click **"Allow"**
4. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)

## Step 2: Install Slack MCP Server

### Option A: Using npm (Recommended)

```bash
# Install globally
npm install -g slack-mcp-server

# Or install locally
npm install slack-mcp-server
```

### Option B: Using npx (No installation required)

```bash
# Use directly without installation
npx slack-mcp-server
```

## Step 3: Configure Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required: Bot User OAuth Token
SLACK_BOT_TOKEN=xoxb-your-bot-token-here

# Optional: App-Level Token (if your MCP server requires it)
SLACK_APP_TOKEN=xapp-your-app-token-here

# Optional: Workspace-specific settings
SLACK_WORKSPACE_ID=T1234567890  # Your workspace ID (optional)
```

## Step 4: Test the Setup

### 4.1 Test MCP Server Connection

```bash
python -m apps.slack_rag \
  --mcp-server "slack-mcp-server" \
  --test-connection \
  --workspace-name "Your Workspace Name"
```

This will test the connection and list available tools without indexing any data.

### 4.2 Index a Specific Channel

```bash
python -m apps.slack_rag \
  --mcp-server "slack-mcp-server" \
  --workspace-name "Your Workspace Name" \
  --channels general \
  --query "What did we discuss about the project?"
```

### 4.3 Real RAG Query Example

To ask intelligent questions about your Slack conversations:

```bash
# Ask about a specific topic discussed in your channels
python -m apps.slack_rag \
  --mcp-server "slack-mcp-server" \
  --workspace-name "Sky Lab Computing" \
  --channels random general \
  --query "What is LEANN about?"
```

This will:
1. **Retrieve relevant messages** from the specified channels
2. **Index the content** for semantic search
3. **Generate an intelligent answer** based on the retrieved context
4. **Provide citations** showing which messages were used

## Success Example: Working Integration

Here's what a successful Slack integration looks like in practice:

### Terminal Output

When you run the connection test, you should see output similar to this:

```
Testing Slack MCP Connection...
Environment: SLACK_MCP_XOXP_TOKEN = xoxb-16753592806-967...

Connected to Slack MCP server!
Authenticated with Slack.

Listing available MCP tools...
Found 5 available tools:
  1. channels_list - Get list of channels
  2. conversations_add_message - Add messages to channels
  3. conversations_history - Get messages from channels
  4. conversations_replies - Get thread messages
  5. conversations_search_messages - Search messages with filters

Testing message fetch from 'random' channel...
Successfully fetched messages from channel random.
```
### Visual Example

The following screenshot shows a successful integration with VS Code displaying the retrieved Slack channel data:

![Slack Integration Success](slack-integration-success.png)

### Key Success Indicators

- **Authentication Success**: Connected to your Slack workspace
- **Tool Availability**: 5 MCP tools ready for interaction
- **Data Access**: Retrieved channel directory with member counts and purposes
- **Comprehensive Coverage**: Access to multiple channels including specialized research groups

This demonstrates that your Slack integration is fully functional and ready for RAG queries across your entire workspace.

### Important: Invite Your Bot to Channels

Before running RAG queries, you need to invite your Slack bot to the channels you want to access. This is a security feature in Slack.

**To invite your bot to a channel:**

1. Go to the channel in Slack (e.g., `#general` or `#random`)
2. Type: `/invite @YourBotName` (replace with your actual bot name)
3. Or click the channel name → "Settings" → "Integrations" → "Add apps"

## Common Issues and Solutions

### Issue 1: "users cache is not ready yet" Error

**Problem**: You see this warning:
```
WARNING - Failed to fetch messages from channel random: Failed to fetch messages: {'code': -32603, 'message': 'users cache is not ready yet, sync process is still running... please wait'}
```

**Solution**: This is a common timing issue. The LEANN integration now includes automatic retry logic:

1. **Wait and Retry**: The system will automatically retry with exponential backoff (2s, 4s, 8s, etc.)
2. **Increase Retry Parameters**: If needed, you can customize retry behavior:
   ```bash
   python -m apps.slack_rag \
     --mcp-server "slack-mcp-server" \
     --max-retries 10 \
     --retry-delay 3.0 \
     --channels general \
     --query "Your query here"
   ```
3. **Keep MCP Server Running**: Start the MCP server separately and keep it running:
   ```bash
   # Terminal 1: Start MCP server
   slack-mcp-server

   # Terminal 2: Run LEANN (it will connect to the running server)
   python -m apps.slack_rag --mcp-server "slack-mcp-server" --channels general --query "test"
   ```

### Issue 2: "No message fetching tool found"

**Problem**: The MCP server doesn't have the expected tools.

**Solution**:
1. Check if your MCP server is properly installed and configured
2. Verify your Slack tokens are correct
3. Try a different MCP server implementation
4. Check the MCP server documentation for required configuration

### Issue 3: Permission Denied Errors

**Problem**: You get permission errors when trying to access channels.

**Solutions**:
1. **Check Bot Permissions**: Ensure your bot has been added to the channels you want to access
2. **Verify Token Scopes**: Make sure you have all required scopes configured
3. **Channel Access**: For private channels, the bot needs to be explicitly invited
4. **Workspace Permissions**: Ensure your Slack app has the necessary workspace permissions

### Issue 4: Empty Results

**Problem**: No messages are returned even though the channel has messages.

**Solutions**:
1. **Check Channel Names**: Ensure channel names are correct (without the # symbol)
2. **Verify Bot Access**: Make sure the bot can access the channels
3. **Check Date Ranges**: Some MCP servers have limitations on message history
4. **Increase Message Limits**: Try increasing the message limit:
   ```bash
   python -m apps.slack_rag \
     --mcp-server "slack-mcp-server" \
     --channels general \
     --max-messages-per-channel 1000 \
     --query "test"
   ```

## Advanced Configuration

### Custom MCP Server Commands

If you need to pass additional parameters to your MCP server:

```bash
python -m apps.slack_rag \
  --mcp-server "slack-mcp-server --token-file /path/to/tokens.json" \
  --workspace-name "Your Workspace" \
  --channels general \
  --query "Your query"
```

### Multiple Workspaces

To work with multiple Slack workspaces, you can:

1. Create separate apps for each workspace
2. Use different environment variables
3. Run separate instances with different configurations

### Performance Optimization

For better performance with large workspaces:

```bash
python -m apps.slack_rag \
  --mcp-server "slack-mcp-server" \
  --workspace-name "Your Workspace" \
  --max-messages-per-channel 500 \
  --no-concatenate-conversations \
  --query "Your query"
```

### Screenshot: Real RAG Query Results

Here's what you'll see when running a RAG query on your Slack workspace:

![RAG Query Results](rag-query-results.png)

**What this screenshot shows:**
- ✅ **Successful MCP connection** to Slack workspace
- ✅ **Channel directory retrieval** (107 channels discovered)
- ✅ **Proper error handling** for channel access permissions
- ⚠️ **"not_in_channel" errors** indicating bot needs invitation to specific channels

This is the expected behavior - the integration is working perfectly, it just needs proper channel permissions to access conversation messages.

## Real RAG Query Example (Sky Lab Computing “random”)

This example shows a real query against the Sky Lab Computing workspace’s “random” channel using the Slack MCP server, with an embedded screenshot of the terminal output.

### Screenshot

![Sky Random RAG](videos/rag-sky-random.png)

### Prerequisites

- Bot is installed in the Sky Lab Computing workspace and invited to the target channel (run `/invite @YourBotName` in the channel if needed)
- Bot token available and exported in the same terminal session

### Commands

1) Set the workspace token for this shell

```bash
export SLACK_MCP_XOXP_TOKEN="xoxb-***-redacted-***"
```

2) Run a real query against the “random” channel by channel ID (C0GN5BX0F)

```bash
python test_channel_by_id_or_name.py \
  --channel-id C0GN5BX0F \
  --workspace-name "Sky Lab Computing" \
  --query "PUBPOL 290"
```

Expected: The output contains a matching message (e.g., “do we have a channel for class PUBPOL 290 this semester?”) followed by a compact RAG-style answer section.

3) Optional: Ask a broader question

```bash
python test_channel_by_id_or_name.py \
  --channel-id C0GN5BX0F \
  --workspace-name "Sky Lab Computing" \
  --query "What is LEANN about?"
```

Notes:
- If you see `not_in_channel`, invite the bot to the channel and re-run.
- If you see `channel_not_found`, confirm the channel ID and workspace.
- Deep search via server-side “search” tools may require additional Slack scopes; the example above performs client-side filtering over retrieved history.

---

## Troubleshooting Checklist

- [ ] Slack app created with proper permissions
- [ ] Bot token (xoxb-) copied correctly
- [ ] App-level token (xapp-) created if needed
- [ ] MCP server installed and accessible
- [ ] Environment variables set correctly
- [ ] Bot invited to relevant channels
- [ ] Channel names specified without # symbol
- [ ] Sufficient retry attempts configured
- [ ] Network connectivity to Slack APIs

## Getting Help

If you continue to have issues:

1. **Check Logs**: Look for detailed error messages in the console output
2. **Test MCP Server**: Use `--test-connection` to verify the MCP server is working
3. **Verify Tokens**: Double-check that your Slack tokens are valid and have the right scopes
4. **Community Support**: Reach out to the LEANN community for help

## Example Commands

### Basic Usage
```bash
# Test connection
python -m apps.slack_rag --mcp-server "slack-mcp-server" --test-connection

# Index specific channels
python -m apps.slack_rag \
  --mcp-server "slack-mcp-server" \
  --workspace-name "My Company" \
  --channels general random \
  --query "What did we decide about the project timeline?"
```

### Advanced Usage
```bash
# With custom retry settings
python -m apps.slack_rag \
  --mcp-server "slack-mcp-server" \
  --workspace-name "My Company" \
  --channels general \
  --max-retries 10 \
  --retry-delay 5.0 \
  --max-messages-per-channel 2000 \
  --query "Show me all decisions made in the last month"
```
