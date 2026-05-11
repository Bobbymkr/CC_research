const fs = require("node:fs/promises");
const path = require("node:path");

const GENERIC_LABELS = new Set([
  "ABC",
  "Any",
  "Enum",
  "None",
  "Path",
  "bool",
  "dict",
  "float",
  "int",
  "list",
  "object",
  "set",
  "str",
  "tuple",
]);

function normalizePath(value) {
  return String(value || "").replace(/\\/g, "/");
}

function canonicalizeLabel(value) {
  return String(value || "")
    .replace(/\r?\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function basename(value) {
  return path.posix.basename(normalizePath(value));
}

function shortSourceFile(sourceFile) {
  const normalized = normalizePath(sourceFile);
  if (!normalized) {
    return "unknown";
  }

  const parts = normalized.split("/").filter(Boolean);
  const base = parts.at(-1) || "unknown";
  if (base === "__init__.py") {
    const parent = parts.at(-2) || "package";
    return `${parent}/__init__.py`;
  }
  return base;
}

function sourceContext(sourceFile) {
  const normalized = normalizePath(sourceFile);
  if (!normalized) {
    return "unknown";
  }

  const parts = normalized.split("/").filter(Boolean);
  const base = parts.at(-1) || "unknown";
  const parent = parts.at(-2);
  return parent ? `${parent}/${base}` : base;
}

function looksLikeFileName(label) {
  return /^[^/\\]+\.[A-Za-z0-9]+$/.test(label);
}

function hasSourceContextSuffix(label) {
  return /\s\[[^[\]]+\]$/.test(label);
}

function collapseRepeatedSourceContext(label) {
  let current = canonicalizeLabel(label);
  const duplicateSuffix = /(\s\[[^[\]]+\])(?:\s+\1)+$/;
  while (duplicateSuffix.test(current)) {
    current = current.replace(duplicateSuffix, "$1");
  }
  return current;
}

function looksLikeNarrativeLabel(label) {
  return (
    label.length > 72 ||
    /^[A-Z][a-z]+ /.test(label) ||
    /^#\s*NOTE:/i.test(label) ||
    label.includes("  ") ||
    label.includes(": ") ||
    label.endsWith(".")
  );
}

function buildBaseDisplayLabel(node) {
  const label = collapseRepeatedSourceContext(
    canonicalizeLabel(node.original_label || node.raw_label || node.label || node.id),
  );
  if (!label) {
    return String(node.id || "unnamed-node");
  }

  if (node.file_type === "rationale") {
    return `${shortSourceFile(node.source_file)} note ${node.source_location || ""}`.trim();
  }

  if (label === "__init__.py" && node.source_file) {
    return shortSourceFile(node.source_file);
  }

  if (hasSourceContextSuffix(label)) {
    return label;
  }

  if (looksLikeNarrativeLabel(label)) {
    return `${shortSourceFile(node.source_file)} note ${node.source_location || ""}`.trim();
  }

  return label;
}

function nodeDisplayPriority(node) {
  const label = canonicalizeLabel(node.display_label || node.label || "");
  const labelBase = label.replace(/\s\[[^[\]]+\]$/, "");
  if (node.file_type === "rationale") {
    return 4;
  }
  if (GENERIC_LABELS.has(labelBase)) {
    return 1;
  }
  if (looksLikeFileName(labelBase)) {
    return 2;
  }
  return 0;
}

function compareCommunityNodes(a, b) {
  return (
    nodeDisplayPriority(a) - nodeDisplayPriority(b) ||
    (b.degree || 0) - (a.degree || 0) ||
    a.display_label.localeCompare(b.display_label)
  );
}

function uniqueLabels(nodes, limit) {
  const labels = [];
  const seen = new Set();
  for (const node of nodes) {
    const label = node.display_label;
    if (!label || seen.has(label)) {
      continue;
    }
    seen.add(label);
    labels.push(label);
    if (labels.length >= limit) {
      break;
    }
  }
  return labels;
}

function buildCommunityNodesLine(nodes) {
  const topLabels = uniqueLabels([...nodes].sort(compareCommunityNodes), 8);
  const remaining = Math.max(nodes.length - topLabels.length, 0);
  return remaining > 0
    ? `${topLabels.join(", ")} (+${remaining} more)`
    : topLabels.join(", ");
}

function replaceSection(text, startMarker, endMarker, replacementBody) {
  const startIndex = text.indexOf(startMarker);
  const endIndex = text.indexOf(endMarker, startIndex);
  if (startIndex === -1 || endIndex === -1) {
    return text;
  }

  return (
    text.slice(0, startIndex + startMarker.length) +
    replacementBody +
    text.slice(endIndex)
  );
}

function parseJsonArrayFromHtml(html, variableName, nextToken) {
  const pattern = new RegExp(
    `const ${variableName} = (\\[[\\s\\S]*?\\]);\\s*${nextToken}`,
    "m",
  );
  const match = html.match(pattern);
  if (!match) {
    throw new Error(`Could not locate ${variableName} in graph.html`);
  }
  return {
    match,
    value: JSON.parse(match[1]),
  };
}

function updateCommunityHeadings(markdown, communityLabels, communityNodes) {
  return markdown.replace(
    /### Community (\d+) - "[^"]*"\nCohesion: ([^\n]+)\nNodes \((\d+)\): [^\n]*/g,
    (_, communityIdText, cohesionText) => {
      const communityId = Number(communityIdText);
      const nodes = communityNodes.get(communityId) || [];
      const label = communityLabels.get(communityId) || `Community ${communityId}`;
      const count = nodes.length;
      const nodeLine = buildCommunityNodesLine(nodes);
      return `### Community ${communityId} - "${label}"\nCohesion: ${cohesionText}\nNodes (${count}): ${nodeLine}`;
    },
  );
}

function updateThinCommunities(markdown, communityLabels, communityNodes) {
  return markdown.replace(
    /- \*\*Thin community `Community (\d+)`\*\* \((\d+) nodes\): [^\n]*\n  Too small to be a meaningful cluster - may be noise or needs more connections extracted\./g,
    (_, communityIdText) => {
      const communityId = Number(communityIdText);
      const nodes = communityNodes.get(communityId) || [];
      const label = communityLabels.get(communityId) || `Community ${communityId}`;
      const nodeLine = buildCommunityNodesLine(nodes);
      return `- **Thin community \`${label}\`** (${nodes.length} nodes): \`${nodeLine}\`\n  Too small to be a meaningful cluster - may be noise or needs more connections extracted.`;
    },
  );
}

async function normalizeGraphOutputs(rootDir = ".") {
  const root = path.resolve(rootDir);
  const graphJsonPath = path.join(root, "graphify-out", "graph.json");
  const graphHtmlPath = path.join(root, "graphify-out", "graph.html");
  const graphReportPath = path.join(root, "graphify-out", "GRAPH_REPORT.md");

  const graphData = JSON.parse(await fs.readFile(graphJsonPath, "utf8"));
  const nodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
  const links = Array.isArray(graphData.links) ? graphData.links : [];

  const degreeById = new Map();
  for (const node of nodes) {
    degreeById.set(node.id, 0);
  }
  for (const link of links) {
    const source = link.source ?? link.from;
    const target = link.target ?? link.to;
    if (degreeById.has(source)) {
      degreeById.set(source, degreeById.get(source) + 1);
    }
    if (degreeById.has(target)) {
      degreeById.set(target, degreeById.get(target) + 1);
    }
  }

  for (const node of nodes) {
    node.degree = degreeById.get(node.id) || 0;
    const stableLabel = collapseRepeatedSourceContext(
      canonicalizeLabel(node.original_label || node.raw_label || node.label || node.id),
    );
    node.original_label = stableLabel;
    node.raw_label = stableLabel;
    node.base_display_label = buildBaseDisplayLabel(node);
  }

  const baseCounts = new Map();
  for (const node of nodes) {
    baseCounts.set(
      node.base_display_label,
      (baseCounts.get(node.base_display_label) || 0) + 1,
    );
  }

  for (const node of nodes) {
    let displayLabel = collapseRepeatedSourceContext(node.base_display_label);
    const context = sourceContext(node.source_file);
    if (
      (baseCounts.get(displayLabel) || 0) > 1 &&
      context !== "unknown" &&
      !hasSourceContextSuffix(displayLabel)
    ) {
      displayLabel = `${displayLabel} [${context}]`;
    }
    displayLabel = collapseRepeatedSourceContext(displayLabel);
    node.display_label = displayLabel;
    node.label = displayLabel;
    node.norm_label = displayLabel.toLowerCase();
  }

  const communityNodes = new Map();
  for (const node of nodes) {
    const communityId = Number(node.community);
    if (!communityNodes.has(communityId)) {
      communityNodes.set(communityId, []);
    }
    communityNodes.get(communityId).push(node);
  }

  const communityLabels = new Map();
  for (const [communityId, communityNodeList] of communityNodes.entries()) {
    const sorted = [...communityNodeList].sort(compareCommunityNodes);
    const label = uniqueLabels(sorted, 3).join(" / ") || `Community ${communityId}`;
    communityLabels.set(communityId, label);
    for (const node of communityNodeList) {
      node.community_name = label;
    }
  }

  await fs.writeFile(graphJsonPath, JSON.stringify(graphData, null, 2), "utf8");

  const html = await fs.readFile(graphHtmlPath, "utf8");
  const rawNodesParsed = parseJsonArrayFromHtml(html, "RAW_NODES", "const RAW_EDGES =");
  const legendParsed = parseJsonArrayFromHtml(html, "LEGEND", "// HTML-escape helper");

  const displayById = new Map(
    nodes.map((node) => [
      node.id,
      {
        label: node.display_label,
        title:
          node.raw_label && node.raw_label !== node.display_label
            ? `${node.display_label}\n${node.raw_label}`
            : node.display_label,
        community_name: communityLabels.get(Number(node.community)) || `Community ${node.community}`,
      },
    ]),
  );

  const normalizedRawNodes = rawNodesParsed.value.map((node) => {
    const display = displayById.get(node.id);
    if (!display) {
      return node;
    }
    return {
      ...node,
      label: display.label,
      title: display.title,
      community_name: display.community_name,
    };
  });

  const normalizedLegend = legendParsed.value.map((entry) => ({
    ...entry,
    label: communityLabels.get(Number(entry.cid)) || entry.label,
  }));

  let updatedHtml = html.replace(
    rawNodesParsed.match[1],
    JSON.stringify(normalizedRawNodes),
  );
  updatedHtml = updatedHtml.replace(
    legendParsed.match[1],
    JSON.stringify(normalizedLegend),
  );
  await fs.writeFile(graphHtmlPath, updatedHtml, "utf8");

  let report = (await fs.readFile(graphReportPath, "utf8")).replace(/\r\n/g, "\n");
  const reportCommunityIds = [...report.matchAll(/### Community (\d+) - /g)].map((match) =>
    Number(match[1]),
  );

  if (reportCommunityIds.length > 0) {
    const hubsBody =
      "\n" +
      reportCommunityIds
        .map((communityId) => {
          const label = communityLabels.get(communityId) || `Community ${communityId}`;
          return `- [[_COMMUNITY_Community ${communityId}|${label}]]`;
        })
        .join("\n") +
      "\n\n";
    report = replaceSection(report, "## Community Hubs (Navigation)\n", "## God Nodes", hubsBody);
  }

  report = report.replace(
    /- \d+ nodes .* \d+ edges .* \d+ communities detected/g,
    `- ${nodes.length} nodes · ${links.length} edges · ${communityLabels.size} communities detected`,
  );

  report = updateCommunityHeadings(report, communityLabels, communityNodes);

  const isolatedNodes = nodes
    .filter((node) => (node.degree || 0) <= 1)
    .sort(compareCommunityNodes);
  const isolatedLine =
    isolatedNodes
      .slice(0, 5)
      .map((node) => `\`${node.display_label}\``)
      .join(", ") + (isolatedNodes.length > 5 ? ` (+${isolatedNodes.length - 5} more)` : "");
  report = report.replace(
    /- \*\*\d+ isolated node\(s\):\*\* [^\n]*/g,
    `- **${isolatedNodes.length} isolated node(s):** ${isolatedLine}`,
  );

  report = updateThinCommunities(report, communityLabels, communityNodes);

  await fs.writeFile(graphReportPath, report, "utf8");

  return {
    graphJsonPath,
    graphHtmlPath,
    graphReportPath,
    normalizedNodes: nodes.length,
    communities: communityLabels.size,
  };
}

module.exports = {
  normalizeGraphOutputs,
};

if (require.main === module) {
  normalizeGraphOutputs(process.argv[2] || ".")
    .then((result) => {
      console.log(
        `Normalized ${result.normalizedNodes} nodes across ${result.communities} communities.`,
      );
    })
    .catch((error) => {
      console.error(error instanceof Error ? error.stack || error.message : String(error));
      process.exitCode = 1;
    });
}
