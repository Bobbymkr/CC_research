"""
RAASA Graphify Full Pipeline — using exact graphify API signatures.
Run from project root: python graphify-out/_run_graphify_full.py
"""
import json
from pathlib import Path

ROOT = Path(".")

# ── Step 2: Detect ──────────────────────────────────────────────────────────
print("\n[Step 2] Detecting project corpus...")
from graphify.detect import detect
corpus = detect(ROOT)
Path("graphify-out/.graphify_detect.json").write_text(json.dumps(corpus))

code_files  = corpus["files"].get("code",     [])
doc_files   = corpus["files"].get("document", [])
paper_files = corpus["files"].get("paper",    [])
all_files   = corpus["files"]
print("  %d code | %d docs | %d papers | %d total words" % (
    len(code_files), len(doc_files), len(paper_files), corpus.get("total_words", 0)))

# ── Step 3A: AST extraction (code) ──────────────────────────────────────────
print("\n[Step 3A] AST extraction from code files...")
from graphify.extract import collect_files, extract, load_cached, save_cached

def to_paths(file_list):
    result = []
    for f in file_list:
        p = Path(f)
        if p.is_dir():
            result.extend(collect_files(p))
        elif p.exists():
            result.append(p)
    return result

code_paths = to_paths(code_files)
ast_result = extract(code_paths) if code_paths else {"nodes": [], "edges": []}
Path("graphify-out/.graphify_ast.json").write_text(json.dumps(ast_result, indent=2))
print("  AST: %d nodes, %d edges" % (len(ast_result["nodes"]), len(ast_result["edges"])))

# ── Step 3B: Semantic extraction (docs + papers) ─────────────────────────────
print("\n[Step 3B] Semantic extraction for docs/papers...")
doc_paths = to_paths(doc_files + paper_files)

all_chunks = []
# Collect AST chunks as the first set
if ast_result["nodes"]:
    all_chunks.append(ast_result)

# For each doc: try cache first, else extract
uncached_paths = []
for p in doc_paths:
    cached = load_cached(p, ROOT)   # returns dict | None
    if cached is not None:
        all_chunks.append(cached)
    else:
        uncached_paths.append(p)

print("  Cache hits: %d | To extract: %d" % (len(doc_paths) - len(uncached_paths), len(uncached_paths)))

BATCH = 80
for i in range(0, len(uncached_paths), BATCH):
    batch = uncached_paths[i:i+BATCH]
    try:
        result = extract(batch)
        all_chunks.append(result)
        for p in batch:
            save_cached(p, result, ROOT)
    except Exception as ex:
        print("  Batch error: %s" % str(ex)[:120])
    done = min(i+BATCH, len(uncached_paths))
    print("  Docs extracted: %d/%d" % (done, len(uncached_paths)))

print("  Total chunks to merge: %d" % len(all_chunks))

# ── Step 4A: Build graph ─────────────────────────────────────────────────────
print("\n[Step 4A] Building combined knowledge graph...")
from graphify.build import build, build_merge, validate_extraction

# Flatten all chunks into single list for validate
flat = {"nodes": [], "edges": []}
for c in all_chunks:
    flat["nodes"].extend(c.get("nodes", []))
    flat["edges"].extend(c.get("edges", []))

validate_extraction(flat)
# build() takes list of extraction dicts
G = build(all_chunks)
print("  Graph: %d nodes, %d edges" % (G.number_of_nodes(), G.number_of_edges()))

# Also write graph JSON for incremental updates
import networkx as nx
from graphify.build import build_merge
# Save graph using networkx link data
graph_data = nx.node_link_data(G)
Path("graphify-out/graph.json").write_text(json.dumps(graph_data, indent=2))

# ── Step 4B: Cluster ─────────────────────────────────────────────────────────
print("\n[Step 4B] Clustering graph into communities...")
from graphify.cluster import cluster, score_all

communities = cluster(G)                  # dict[int, list[str]]
cohesion    = score_all(G, communities)   # dict[int, float]

Path("graphify-out/.graphify_partition.json").write_text(json.dumps({
    "communities": communities, "cohesion": cohesion
}, indent=2))

print("  Communities: %d" % len(communities))
for cid in sorted(communities):
    members = communities[cid]
    print("    C%d: %d nodes  cohesion=%.3f" % (cid, len(members), cohesion.get(cid, 0)))

# ── Step 5: Build community labels ───────────────────────────────────────────
print("\n[Step 5] Labeling communities...")
community_labels = {}
for cid, members in communities.items():
    # Use top degree nodes as label
    degree_sorted = sorted(members, key=lambda n: G.degree(n) if n in G else 0, reverse=True)
    top_names = []
    for nid in degree_sorted[:3]:
        nd = G.nodes.get(nid, {})
        top_names.append(nd.get("label", nd.get("name", str(nid)))[:25])
    community_labels[cid] = " / ".join(top_names) if top_names else "Community %d" % cid
    print("    C%d label: %s" % (cid, community_labels[cid]))

# ── Step 6: Analyze ───────────────────────────────────────────────────────────
print("\n[Step 6] Analyzing god nodes, surprising connections, questions...")
from graphify.analyze import god_nodes, surprising_connections, suggest_questions

gods      = god_nodes(G, top_n=10)
surp      = surprising_connections(G, communities, top_n=8)
questions = suggest_questions(G, communities, community_labels, top_n=10)

Path("graphify-out/.graphify_analysis.json").write_text(json.dumps({
    "god_nodes": gods,
    "surprising_connections": surp,
    "suggested_questions": questions,
}, indent=2))
print("  God nodes: %s" % ", ".join([g.get("id", "?") for g in gods[:5]]))
print("  Surprising connections: %d" % len(surp))
print("  Suggested questions: %d" % len(questions))

# ── Step 7: Generate GRAPH_REPORT.md ─────────────────────────────────────────
print("\n[Step 7] Generating GRAPH_REPORT.md...")
from graphify.report import generate

token_cost = {
    "input_tokens":  ast_result.get("input_tokens", 0),
    "output_tokens": ast_result.get("output_tokens", 0),
}

report_md = generate(
    G,
    communities=communities,
    cohesion_scores=cohesion,
    community_labels=community_labels,
    god_node_list=gods,
    surprise_list=surp,
    detection_result=corpus,
    token_cost=token_cost,
    root=str(ROOT),
    suggested_questions=questions,
)
Path("graphify-out/GRAPH_REPORT.md").write_text(report_md, encoding="utf-8")
print("  Report written: graphify-out/GRAPH_REPORT.md (%d chars)" % len(report_md))

# ── Step 9: Save manifest ─────────────────────────────────────────────────────
print("\n[Step 9] Saving manifest...")
from graphify.manifest import save_manifest

save_manifest(all_files, manifest_path="graphify-out/manifest.json")
print("  Manifest saved: graphify-out/manifest.json")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("GRAPHIFY COMPLETE")
print("="*60)
print("  Nodes        : %d" % G.number_of_nodes())
print("  Edges        : %d" % G.number_of_edges())
print("  Communities  : %d" % len(communities))
print("  God nodes    : %d" % len(gods))
print("  Report       : graphify-out/GRAPH_REPORT.md")
print("="*60)
