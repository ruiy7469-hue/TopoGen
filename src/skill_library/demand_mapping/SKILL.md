---
name: demand-mapping
description: Maps high-level traffic demand matrices into discrete, executable vehicle trip files (.rou.xml).
usage: Use after the road network (.net.xml) is synthesized to define traffic volume and vehicle composition.
---

# Skill: Demand Mapping
This skill populates the simulation environment with heterogeneous traffic flows (Car, Truck, etc.).

### Arguments:
- `net_file`: Path to the compiled network.
- `flow_configs`: List of OD pairs and volumes.

### Output:
- Generates `traffic.rou.xml` and `detectors.add.xml`.