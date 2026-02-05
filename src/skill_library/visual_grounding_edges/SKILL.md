---
name: visual-grounding-edges
description: Renders the Graph-based Intermediate Representation (GIR) into a directed topological graph. Use this to provide visual feedback to the user after the initial synthesis or refinement.
allowed-tools: matplotlib, networkx
---

# Skill: Visual Grounding (Edges)
This skill bridges the gap between abstract topological tensors and human visual intuition. It maps the `node_coordinates` and `adjacency_matrix` into a 2D canvas.

### Execution Logic:
- **Node Rendering**: Draws gray circular nodes with explicit IDs.
- **Edge Rendering**: Draws blue directed arrows. Implements a transverse offset logic to prevent overlapping in bidirectional roads.
- **Scaling**: Includes a 100m scale bar anchored to the geographic bounding box.

### Arguments:
- `node_coords`: Tier-1 Explicit Entity Tensor (Coordinates).
- `adj_matrix`: Tier-2 Logical Dependency Tensor (Connectivity).