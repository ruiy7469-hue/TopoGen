---
name: visual-grounding-tls
description: Highlights signalized junctions (Traffic Light Systems) on the road network graph. Use this during the fine-tuning phase to show where signal logic has been orchestrated.
allowed-tools: matplotlib
---

# Skill: Visual Grounding (TLS)
This skill provides a spatial audit of traffic control devices. It overlays red square markers on junctions with a degree $\ge 3$ or those explicitly assigned a controller.

### Execution Logic:
- **Base Layer**: Renders the standard road network edges.
- **Highlight Layer**: Identifies nodes in `tls_nodes` and renders them as distinctive red squares to facilitate signal timing calibration.

### Arguments:
- `node_coords`: List of node positions.
- `adj_matrix`: Connectivity matrix.
- `tls_nodes`: Dictionary mapping node IDs to traffic light IDs.