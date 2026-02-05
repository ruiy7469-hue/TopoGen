---
name: metadata-ingestion
description: Parses physical simulation artifacts (.net.xml) to extract metadata. Use this to synchronize the agent's internal GIR state with the deterministically generated environment.
allowed-tools: xml.etree.ElementTree
---

# Skill: Metadata Ingestion
This skill performs a "reverse-mapping" from the physical XML domain back to the agent's reasoning layer. It ensures the Auditor and user are working with the actual compiled network data.

### Functionality:
1. **Junction Scanning**: Identifies junctions typed as `traffic_light`.
2. **Logic Extraction**: Parses `tlLogic` blocks for phase sequences and state strings.
3. **Connection Binding**: Maps controlled lanes to specific signal link indices.

### Arguments:
- `net_file`: Path to the compiled SUMO network file.