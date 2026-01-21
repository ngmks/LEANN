# LEANN - The smallest vector index in the world

LEANN is a revolutionary vector database that democratizes personal AI. Transform your laptop into a powerful RAG system that can index and search through millions of documents while using **97% less storage** than traditional solutions **without accuracy loss**.

## Installation

### Standard Installation (Local Development)

```bash
# Install core package only
pip install leann

# Or install with backends (requires building from source)
# See "Building from Source" section below
```

### Docker Installation

The backend packages (`leann-backend-hnsw` and `leann-backend-diskann`) require compilation and are not available on PyPI. For Docker installations, you have two options:

#### Option 1: Install Core Only (No Backends)

```dockerfile
FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install LEANN core
RUN pip install leann

# Note: Backends must be built from source (see Option 2)
```

#### Option 2: Build Backends from Source

```dockerfile
FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    swig \
    && rm -rf /var/lib/apt/lists/*

# Clone LEANN repository
WORKDIR /app
RUN git clone https://github.com/yichuan-w/LEANN.git .

# Install core first
RUN pip install ./packages/leann-core

# Build and install HNSW backend
RUN pip install ./packages/leann-backend-hnsw

# Build and install DiskANN backend (optional)
RUN pip install ./packages/leann-backend-diskann
```

### Building from Source (Local)

If you need the backends and they're not available as pre-built wheels:

```bash
# Clone the repository
git clone https://github.com/yichuan-w/LEANN.git
cd LEANN

# Install core
pip install ./packages/leann-core

# Build and install HNSW backend
pip install ./packages/leann-backend-hnsw

# Build and install DiskANN backend (optional)
pip install ./packages/leann-backend-diskann
```

## Quick Start

```python
from leann import LeannBuilder, LeannSearcher, LeannChat
from pathlib import Path
INDEX_PATH = str(Path("./").resolve() / "demo.leann")

# Build an index (choose backend: "hnsw" or "diskann")
builder = LeannBuilder(backend_name="hnsw")  # or "diskann" for large-scale deployments
builder.add_text("LEANN saves 97% storage compared to traditional vector databases.")
builder.add_text("Tung Tung Tung Sahur called—they need their banana‑crocodile hybrid back")
builder.build_index(INDEX_PATH)

# Search
searcher = LeannSearcher(INDEX_PATH)
results = searcher.search("fantastical AI-generated creatures", top_k=1)

# Chat with your data
chat = LeannChat(INDEX_PATH, llm_config={"type": "hf", "model": "Qwen/Qwen3-0.6B"})
response = chat.ask("How much storage does LEANN save?", top_k=1)
```

## License

MIT License
