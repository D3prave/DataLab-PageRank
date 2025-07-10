# Academic Citation Crawler & Dashboard

This project implements a scalable academic citation crawler powered by the Semantic Scholar API. It supports efficient deduplication using RedisBloom, structured storage in PostgreSQL, and real-time monitoring with a FastAPI dashboard, including memory stats from remote instances via SSH.

---

## 📚 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [How to Run](#-how-to-run)
- [Crawler Script (`crawler.py`)](#-crawlerpy)
- [Dashboard Script (`dashboard.py`)](#-dashboardpy)
- [Remote Service Controller Script (`start_stop_crawler.py`)](#-start_stop_crawlerpy)
- [Author Paper Fetcher (`fetch_author_papers.py`)](#-fetch_author_paperspy)
- [API & Interfaces](#-api--interfaces)
- [Technologies Used](#-technologies-used)
- [Requirements](#-requirements)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)

---

## 📌 Overview

This project implements a robust academic crawler to collect citation data via the [Semantic Scholar API](https://api.semanticscholar.org/). The data is processed, stored in PostgreSQL, and de-duplicated using Redis with a Bloom filter. A live dashboard (FastAPI) monitors crawler performance and remote server resources.

---

## ✨ Features

- ✅ Distributed crawling with queue-based task management
- 🚦 Queue management with Redis and JSON-encoded payloads
- 🧠 Deduplication with Redis Bloom filters + SQL fallback
- 🔁 Retry logic with exponential backoff using tenacity
- 🕸️ Citation graph generation (directed edges) with pagination for large papers
- 📊 Real-time dashboard with memory, rate, and paper stats
- 📦 Background memory checks on remote servers via SSH

---

## 🕷️ crawler.py

The main script that handles fetching, deduplication, citation parsing, and task queue management.

### 🧩 Key Components

- ⚡ send_request: Rate-limited API requests with retry logic
- 📜 fetch_references_paginated: Handles large reference sets (>1000)
- 🧠 filter_new_ids: Bloom filter + SQL fallback deduplication
- 🔒 safe_insert_citations: Robust insert with deadlock handling
- 🏷️ mark_processed: Marks paper as crawled in both Redis and SQL
- ▶ main(): Main crawl loop with seed support, resume, and batching

### ▶ How to Use

Start a **fresh** crawl with seed IDs:
```bash
python crawler.py --fresh <seed_id1> <seed_id2>
```
Resume a previously interrupted crawl:
```bash
python crawler.py --resume
```

---

## 📊 dashboard.py

A FastAPI app providing real-time monitoring for crawler performance and system resource usage.

### 📡 Endpoints

- 🌐 GET - HTML Dashboard UI
- 📈 GET /status - Returns crawler metrics as JSON
  
### 📈 Metrics Shown

- ✅ Number of processed papers
- 🔗 Citation edges discovered
- 🧠 Memory pressure (macOS local)
- 🧠 RAM usage on remote servers via SSH
- ⚡ Papers/second & 📈 papers/hour
- 🕒 Estimated time per 1000 papers

### 🧵 Background Tasks

- ⏲️ remote_ram_background_updater() – polls RAM usage every 60s
- ⏲️ speed_background_updater() – updates crawl rate every 15s

### ▶ How to Use

Run the **Dashboard** server:
```bash
uvicorn dashboard:app --host 0.0.0.0 --port xxxx --reload
```

---
## 🛑 start_stop_crawler.py

This utility script manages the crawler.service systemd unit on multiple remote servers via SSH. It allows you to start or stop the crawler daemon across all instances with a single command.

### 🔧 Configuration

The script uses a dictionary (HOST_KEY_MAP) to map server IPs to their corresponding private SSH key files:
```
HOST_KEY_MAP = {
    "IP": "KEY",
    "IP": "KEY",
    "IP": "KEY",
}
```
Make sure all key files are present and accessible.
  
### ▶ How to Use

Start the crawler.service on all configured remote hosts:
```
python start_stop_crawler.py --on
```
Stop the crawler.service.
```
python start_stop_crawler.py --off
```

### ⚠️ Note

Remote servers must have:
- 🔐 SSH access enabled
- 🛠️ Python systemd unit defined as crawler.service

Local machine must have:
- 🔑 Private SSH key access for each host
- 📦 paramiko installed

---

## 🧾 fetch_author_papers.py

This utility script fetches papers written by specific authors from the Semantic Scholar API. It saves:
- 📝 Detailed metadata in a CSV file (papers_by_authors.csv)
- 🆔 Paper IDs only in a plain text file (paper_ids.txt) for seeding the crawler

### ▶ How to Use

Edit the author_ids list in the script to include the authors you are interested in:

```
author_ids = [
    "ID1", "ID2", "ID3", ...
]
```

---

## 🧮 PageRank Computation (HPC_graph_tool.py)

This script computes PageRank scores on the full citation graph using the high-performance graph-tool library, suitable for large-scale academic datasets and HPC environments. It:
- 🏗️ Builds a directed graph from citation edges
- 📈 Computes PageRank using graph_tool.pagerank()
- 🎯 Normalizes scores to sum = 1
- 🔗 Joins PageRank values with metadata

### Inputs

- `--input`: CSV file containing citation edges with columns: (`citing_id` , `cited_id`)
- `--metadata`: CSV file with metadata for papers, containing: (`paper_id`, `fields_of_study`)
- `--output`: Output directory to store logs, results, and graph file

### Outputs

- `pagerank_merged.csv`: PageRank scores merged with paper metadata
- `graph.graphml`: GraphML file for visualization
- `pagerank.log`: Execution logs

### ⚠️ Note

- ⚡ This computation was run on a supercomputer using SLURM job scheduling due to the large size of the citation graph (millions of nodes and edges).
- 🐳 The environment was containerized with Docker, ensuring consistent dependency management and compatibility for graph-tool.

## 🔌 API & Interfaces

### 🌐 Semantic Scholar API
Base URL: https://api.semanticscholar.org/graph/v1
- GET /paper/{id}/references: For paginated citation lists
- POST /paper/batch: For batched paper metadata

### 🔁 Redis
- paper_queue	- FIFO queue of papers to crawl
- processed_bloom	- RedisBloom filter to avoid duplicate paper IDs
- queued_bloom: RedisBloom filter to avoid duplicate enqueueing

### 🗃️ PostgreSQL
- processed_papers - Stores paper_id and its fields_of_study
- citations - Stores directed edges (citing_id → cited_id)

### 🌐 FastAPI Dashboard
- GET - HTML dashboard UI
- GET /status -	Returns system stats in JSON (see below)

---

## 🤖 Technologies Used

- **Python 3**
- **PostgreSQL** (`psycopg2`, `asyncpg`)
- **Redis** + Bloom Filter
- **FastAPI** (Dashboard backend)
- **requests** (API access)
- **asyncssh** (RAM monitoring via SSH)
- **Semantic Scholar API**
- **Tenacity** (for robust retry logic)
- **Uvicorn** (for serving dashboard)
- **paramiko** (for SSH protocols)
- **subprocess/sysctl** (macOS memory pressure)

---

## 📝 Requirements

- crawler.py: requests, redis, psycopg2, tenacity
- dashboard.py: fastapi, uvicorn, asyncssh
- start_stop_crawler.py: paramiko
- fetch_author_papers.py: requests

```
pip install -r requirements.txt
```
---

## 📐 Architecture
```
               +-----------------------+
               |  Semantic Scholar API |
               +----------+------------+
                          |
                          v
               +-----------------------+
               |      Crawler.py       |
               |-----------------------|
               |  - Batched Fetching   |
               |  - Reference Parsing  |
               |  - Deduplication      |
               |  - Queue Handling     |
               +----------+------------+
                          |
           +--------------+--------------+
           |                             |
           v                             v
  +-------------------+       +------------------------+
  |     PostgreSQL    |       |         Redis          |
  |-------------------|       |------------------------|
  |  - Processed IDs  |       |  - Task Queue (FIFO)   |
  |  - Citations      |       |  - Bloom Filter        |
  +-------------------+       +------------------------+
           |
           v
 +--------------------------+
 |      FastAPI Dashboard   |
 |--------------------------|
 | - Crawl Stats            |
 | - Crawl Speed            |
 | - Remote RAM Monitoring  |
 +--------------------------+
           |
           v
 +--------------------------+
 |     Web Browser UI       |
 +--------------------------+
```
---

## 📁 Project Structure
```
.
├── crawler.py
├── dashboard.py
├── fetch_author_papers.py
├── requirements.txt
└── start_stop_crawler.py
```

---
