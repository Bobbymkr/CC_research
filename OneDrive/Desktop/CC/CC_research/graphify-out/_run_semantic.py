import json
from graphify.extract import extract_semantic
from graphify.cache import save_to_cache, check_semantic_cache
from pathlib import Path

uncached = Path("graphify-out/.graphify_uncached.txt").read_text().splitlines()
uncached = [f for f in uncached if f.strip()]

print("Running semantic extraction on %d files..." % len(uncached))

# Batch to avoid memory issues
BATCH = 50
all_nodes, all_edges, all_hyperedges = [], [], []

# Start from cached data if any
try:
    cached = json.loads(Path("graphify-out/.graphify_cached.json").read_text())
    all_nodes = cached.get("nodes", [])
    all_edges = cached.get("edges", [])
    all_hyperedges = cached.get("hyperedges", [])
    print("  Loaded %d cached nodes, %d cached edges" % (len(all_nodes), len(all_edges)))
except Exception:
    pass

for i in range(0, len(uncached), BATCH):
    batch = uncached[i:i+BATCH]
    try:
        result = extract_semantic(batch)
        new_nodes = result.get("nodes", [])
        new_edges = result.get("edges", [])
        new_he    = result.get("hyperedges", [])
        all_nodes.extend(new_nodes)
        all_edges.extend(new_edges)
        all_hyperedges.extend(new_he)
        save_to_cache(batch, new_nodes, new_edges, new_he)
        print("  Batch %d/%d: +%d nodes +%d edges" % (
            min(i+BATCH, len(uncached)), len(uncached), len(new_nodes), len(new_edges)
        ))
    except Exception as e:
        print("  Batch %d/%d: ERROR - %s" % (min(i+BATCH, len(uncached)), len(uncached), str(e)))

Path("graphify-out/.graphify_semantic.json").write_text(json.dumps({
    "nodes": all_nodes, "edges": all_edges, "hyperedges": all_hyperedges
}, indent=2))
print("Semantic done: %d nodes, %d edges, %d hyperedges" % (
    len(all_nodes), len(all_edges), len(all_hyperedges)
))
