---
name: temporal-logic-serialization
description: Serializes traffic light phase data into SUMO additional files.
usage: Use when specific signal timings or actuated logic are defined for intersections.
---

# Skill: Temporal Logic Serialization
Converts Tier-2 logical dependencies related to signal timing into physical XML.

### Arguments:
- `tls_data`: Dictionary containing phase states and durations.

### Output:
- Generates `tls.add.xml`.