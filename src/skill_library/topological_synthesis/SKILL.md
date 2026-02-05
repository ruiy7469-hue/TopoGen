---
name: topological-synthesis
description: Transforms validated Graph-based Intermediate Representation (GIR) into SUMO-compliant .net.xml files. 
usage: Invoke when the Generator-Auditor loop has reached consensus on nodes and adjacency matrices.
---

# Skill: Topological Synthesis
This skill performs the "Entity Instantiation" and "Topology Connection" passes defined in Algorithm 3.

### Arguments:
- `node_coords`: List of [x, y] coordinates.
- `adj_matrix`: N x N directed adjacency matrix.

### Output:
- Generates `network.net.xml` via SUMO `netconvert`.