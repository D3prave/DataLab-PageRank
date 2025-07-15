import os
os.environ["OMP_WAIT_POLICY"] = "passive"

import argparse
import logging
import pandas as pd
import re
from graph_tool.all import Graph, pagerank, openmp_enabled

def setup_logger(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, "pagerank.log")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[
                            logging.FileHandler(log_file),
                            logging.StreamHandler()
                        ])

def clean_id(x):
    return str(x).strip().strip('"')

def clean_fields(x):
    if pd.isna(x):
        return ""
    x = str(x).strip()
    x = x.strip('"').strip('{').strip('}')
    x = re.sub(r'""', '"', x)
    x = x.replace('"', '')
    return x

def load_graph(edge_file):
    logging.info(f"Loading edges from: {edge_file}")
    edges_df = pd.read_csv(edge_file, dtype=str)
    edges_df["citing_id"] = edges_df["citing_id"].apply(clean_id)
    edges_df["cited_id"] = edges_df["cited_id"].apply(clean_id)
    logging.info(f"Edges loaded: {len(edges_df)}")

    logging.info("Building graph-tool graph...")
    nodes = pd.Index(pd.concat([edges_df["citing_id"], edges_df["cited_id"]]).unique())
    id_map = {node: idx for idx, node in enumerate(nodes)}

    g = Graph(directed=True)
    g.add_vertex(len(nodes))
    edge_list = [(id_map[src], id_map[dst]) for src, dst in edges_df.values]
    g.add_edge_list(edge_list)

    logging.info(f"Graph built: {g.num_vertices()} nodes, {g.num_edges()} edges")
    return g, nodes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to citations CSV file")
    parser.add_argument("--metadata", required=True, help="Path to processed CSV file")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    setup_logger(args.output)
    
    logging.info(f"OpenMP enabled: {openmp_enabled()}")
    
    g, nodes = load_graph(args.input)
    graphml_path = os.path.join(args.output, "graph.graphml")
    g.save(graphml_path)
    logging.info(f"Graph saved to {graphml_path}")

    logging.info(f"Running PageRank")
    pr = pagerank(g, damping=0.85)

    pr_sum = pr.a.sum()
    pr.a /= pr_sum
    pr_df = pd.DataFrame({"paper_id": nodes, "pagerank": pr.a})
    logging.info(f"Normalized PageRank sum: {pr.a.sum()}")

    logging.info(f"Loading metadata from: {args.metadata}")
    meta_df = pd.read_csv(args.metadata, dtype=str)
    meta_df["paper_id"] = meta_df["paper_id"].apply(clean_id)
    meta_df["fields_of_study"] = meta_df["fields_of_study"].apply(clean_fields)

    logging.info("Merging PageRank with metadata...")
    merged_df = pr_df.merge(meta_df, on="paper_id", how="left")

    output_file = os.path.join(args.output, "pagerank_merged.csv")
    merged_df.to_csv(output_file, index=False)
    logging.info(f" Final results saved to: {output_file}")

if __name__ == "__main__":
    main()
