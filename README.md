# Academic Citation Crawler, Dashboard & PageRank

A scalable system for collecting academic citation data via the Semantic Scholar API, monitoring crawling performance in real time, and computing PageRank scores on massive citation graphs using high-performance tools like Redis, PostgreSQL, FastAPI, and graph-tool.

---

## 📚 Table of Contents

- [📌 Overview](#-overview)
- [💾 Prerequisite](#-prerequisite)
- [✨ Features](#-features)

### 🐍 Scripts
- [🕷 Crawler Script (`crawler.py`)](#-crawlerpy)
- [📊 Dashboard Script (`dashboard.py`)](#-dashboardpy)
- [🛑 Remote Service Controller Script (`start_stop_crawler.py`)](#-start_stop_crawlerpy)
- [🧾 Author Paper Fetcher (`fetch_author_papers.py`)](#-fetch_author_paperspy)
- [🧮 PageRank Computation (`HPC_graph_tool.py`)](#-hpc_graph_toolpy)

### 📈 PageRank Analysis
- [📘 Full Dataset Citations (full_dataset_citations.ipynb)](#full-dataset-citations-fulldataset_citationsipynb)
- [📗 Full Dataset PageRank (full_dataset_pagerank.ipynb)](#full-dataset-pagerank-fulldataset_pagerankipynb)
- [📙 Manual vs NetworkX (manual_vs_networkx.ipynb)](#manual-vs-networkx-manualvsnetworkxipynb)
- [🌐 Top 1500 Connected Graph (top1500_connected.html)](#top-1500-connected-graph-top1500_connectedhtml)
- [🌐 Top 1500 PageRank Connected Graph (top1500_pagerank_connected.html)](#top-1500-pagerank-connected-graph-top1500_pagerank_connectedhtml)


- [🔌 API & Interfaces](#-api--interfaces)
- [🤖 Technologies Used](#-technologies-used)
- [📝 Requirements](#-requirements)
- [📐 Architecture](#-architecture)
- [📁 Project Structure](#-project-structure)

---

## 📌 Overview

This project implements a full pipeline for crawling and analyzing academic citation data at scale.

At its core is a resilient crawler that retrieves paper metadata and citation relationships from the [Semantic Scholar API](https://api.semanticscholar.org/). It supports queue-based task distribution, deduplication through RedisBloom and PostgreSQL, and robust retry handling with `tenacity`.

To monitor system health and crawling performance, a FastAPI-based dashboard provides real-time stats, including memory usage across remote servers accessed via SSH.

After the crawl is complete, the system launches a high-performance analysis pipeline on the extracted citation graph and its PageRank scores using HPC resources. We leverage graph-tool for scalable graph algorithms, networkx and scipy for efficient network metrics, and pandas for large-scale data handling. For visualization and interactive exploration, we integrate pyvis, matplotlib (optionally styled with seaborn), and plotly. The PageRank computation runs on a supercomputer, producing normalized influence scores that help users quickly identify the most impactful papers based on citation structure.

Additionally, the system includes a custom implementation of the PageRank algorithm using NumPy and sparse matrix operations for improved performance. To validate the algorithm, we extract a small subset of the crawled citation database and compare the output against NetworkX’s built-in PageRank function to ensure correctness. We also evaluate the efficiency of our implementation by measuring and comparing runtime performance with NetworkX.

Together, these components form a modular and extensible platform for academic network analysis — encompassing citation data crawling, custom PageRank computation, and influence-based ranking of papers.

---

## 💾 Prerequisite

Before running the crawler, make sure:
- PostgreSQL is running and a database is created.
- Redis server is running and Bloom filter module is available.

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
## 🐍 Scripts

### 🕷 crawler.py

The main script that handles fetching, deduplication, citation parsing, and task queue management.

#### 🧩 Key Components

- ⚡ send_request: Rate-limited API requests with retry logic
- 📜 fetch_references_paginated: Handles large reference sets (>1000)
- 🧠 filter_new_ids: Bloom filter + SQL fallback deduplication
- 🔒 safe_insert_citations: Robust insert with deadlock handling
- 🏷️ mark_processed: Marks paper as crawled in both Redis and SQL
- 🚀 main(): Main crawl loop with seed support, resume, and batching
 
#### ▶ How to Use

Start a **fresh** crawl with seed IDs:
```bash
python crawler.py --fresh <seed_id1> <seed_id2>
```
Resume a previously interrupted crawl:
```bash
python crawler.py --resume
```

---

### 📊 dashboard.py

A FastAPI app providing real-time monitoring for crawler performance and system resource usage.

#### 📡 Endpoints

- 🌐 GET - HTML Dashboard UI
- 📈 GET /status - Returns crawler metrics as JSON
  
#### 📈 Metrics Shown

- ✅ Number of processed papers
- 🔗 Citation edges discovered
- 🧠 Memory pressure (macOS local)
- 🧠 RAM usage on remote servers via SSH
- ⚡ Papers/second & 📈 papers/hour
- 🕒 Estimated time per 1000 papers

#### 🧵 Background Tasks

- ⏲️ remote_ram_background_updater() – polls RAM usage every 60s
- ⏲️ speed_background_updater() – updates crawl rate every 15s

#### ▶ How to Use

Run the **Dashboard** server:
```bash
uvicorn dashboard:app --host 0.0.0.0 --port xxxx --reload
```

---
### 🛑 start_stop_crawler.py

This utility script manages the crawler.service systemd unit on multiple remote servers via SSH. It allows you to start or stop the crawler daemon across all instances with a single command.

#### 🔧 Configuration

The script uses a dictionary (HOST_KEY_MAP) to map server IPs to their corresponding private SSH key files:
```
HOST_KEY_MAP = {
    "IP": "KEY",
    "IP": "KEY",
    "IP": "KEY",
}
```
Make sure all key files are present and accessible.
  
#### ▶ How to Use

Start the crawler.service on all configured remote hosts:
```
python start_stop_crawler.py --on
```
Stop the crawler.service.
```
python start_stop_crawler.py --off
```

#### ⚠️ Note

Remote servers must have:
- 🔐 SSH access enabled
- 🛠️ Python systemd unit defined as crawler.service

Local machine must have:
- 🔑 Private SSH key access for each host
- 📦 paramiko installed

---

### 🧾 fetch_author_papers.py

This utility script fetches papers written by specific authors from the Semantic Scholar API. It saves:
- 📝 Detailed metadata in a CSV file (papers_by_authors.csv)
- 🆔 Paper IDs only in a plain text file (paper_ids.txt) for seeding the crawler

#### ▶ How to Use

Edit the author_ids list in the script to include the authors you are interested in:

```
author_ids = [
    "ID1", "ID2", "ID3", ...
]
```

---

### 🧮 HPC_graph_tool.py

This script computes PageRank scores on the full citation graph using the high-performance graph-tool library, suitable for large-scale academic datasets and HPC environments. It:
- 🏗️ Builds a directed graph from citation edges
- 📈 Computes PageRank using graph_tool.pagerank()
- 🎯 Normalizes scores to sum = 1
- 🔗 Joins PageRank values with metadata

#### Inputs

- `--input`: CSV file containing citation edges with columns: (`citing_id` , `cited_id`)
- `--metadata`: CSV file with metadata for papers, containing: (`paper_id`, `fields_of_study`)
- `--output`: Output directory to store logs, results, and graph file

#### Outputs

- `pagerank_merged.csv`: PageRank scores merged with paper metadata
- `graph.graphml`: GraphML file for visualization
- `pagerank.log`: Execution logs

#### ⚠️ Note

- ⚡ This computation was run on a supercomputer using SLURM job scheduling due to the large size of the citation graph (millions of nodes and edges).
- 🐳 The environment was containerized with Docker, ensuring consistent dependency management and compatibility for graph-tool.

## 📈 PageRank Analysis

### 📘 full_dataset_citations.ipynb
A Jupyter notebook that performs thorough preprocessing and exploratory analysis prior to PageRank computation.

#### 🔍 Core Tasks

- 📊 Generates statistics like in-degree/out-degree distribution

- 🧱 Constructs the directed graph structure from citing → cited of the top 1500 papers by out-degree

- 🔍 Creates an inter-field citation heatmap

#### 🧯 Purpose
This notebook offers insight into the overall citation dynamics across the dataset.

### 📗 full_dataset_pagerank.ipynb
A Jupyter notebook focused on analyzing and visualizing the results of PageRank computation over the complete academic citation graph.

#### 📌 Key Highlights

- 📥 Loads PageRank scores (from pagerank_merged.csv)

- 🔝 Identifies top-ranked papers by influence

- 📈 Visualizes score distribution

- 🧱 Constructs the directed graph structure from citing → cited of the top 1500 papers by PageRank score

- 📊 Determines top fields by PageRank scores

- 🔍 Computes top-ranked papers and professors of MIDS Catholic University of Eichstaett-Ingolstadt Professors

#### 🎯 Purpose
Helps interpret what PageRank reveals about influence in academic networks, and visually bridges algorithmic output with real-world research impact.

### 📙 manual_vs_networkx.ipynb
A Jupyter notebook comparing the outputs and performance of a custom PageRank implementation with NetworkX's native algorithm.

#### ⚖️ Comparisons Include

- ⏱️ Runtime benchmarks

- 📊 Numerical differences across nodes

- 📈 Visualization of score deviation 

#### 🧠 Takeaways
This notebook helps validate the manual implementation while highlighting performance trade-offs between using NetworkX and lower-level, optimized approaches.

### 🌐 top1500_connected.html
An interactive PyVis graph displaying the 1500 most connected nodes by number of outgoing citations.

#### ✨ Features
- 📌 Nodes sized by out-degree (how many papers they cite)

- 🎨 Color-coded nodes by fields of study

- 🖱️ Hover to view paper id

#### 📈 Use Case
Useful for exploring prolific citing papers and identifying key "bridge" nodes between disciplines or clusters.

### 🌐 top1500_pagerank_connected.html
An interactive PyVis network graph showcasing the 1500 most influential papers ranked by PageRank score.

#### ✨ Features
- 🌟 Node size reflects PageRank score (influence)

- 🎨 Color-coded nodes by fields of study

- 🖱️ Hover to view paper id

#### 🎯 Use Case
Ideal for visualizing PageRank-based academic influence and uncovering hubs of citation authority in the scholarly graph.


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
├── pagerank_analysis/
│   ├── full_dataset_citations.ipynb
│   ├── full_dataset_pagerank.ipynb
│   ├── manual_vs_networkx.ipynb
│   ├── top1500_connected.html
│   └── top1500_pagerank_connected.html
├── scripts/
│   ├── HPC_graph_tool.py
│   ├── crawler.py
│   ├── dashboard.py
│   ├── fetch_author_papers.py
│   ├── requirements.txt
│   └── start_stop_crawler.py
└── README.me
```

---
