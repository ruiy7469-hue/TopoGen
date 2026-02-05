import os
import xml.etree.ElementTree as ET
def run(net_file):
    """Skill: Metadata Ingestion. Parses SUMO network file to retrieve signalized junction logic."""
    if not os.path.exists(net_file):
        return {}, {}

    tree = ET.parse(net_file)
    root = tree.getroot()

    # Mapping junctions to controller IDs
    tls_nodes = {}  # {node_id: tls_id}
    for junc in root.findall("junction"):
        if junc.get("type") == "traffic_light":
            tl_id = junc.get("tl")
            node_id = junc.get("id")
            tls_nodes[node_id] = tl_id

    tls_data = {}
    for tl in root.findall("tlLogic"):
        tl_id = tl.get("id")
        if tl.get("programID") != "0":
            continue

        phases = []
        for ph in tl.findall("phase"):
            phases.append({
                "duration": float(ph.get("duration")),
                "state": ph.get("state"),
                "minDur": float(ph.get("minDur", ph.get("duration"))),
                "maxDur": float(ph.get("maxDur", ph.get("duration")))
            })

        params = {}
        for p in tl.findall("param"):
            params[p.get("key")] = p.get("value")

        tls_data[tl_id] = {
            "type": tl.get("type", "static"),
            "cycle": sum(p["duration"] for p in phases),
            "offset": float(tl.get("offset", 0)),
            "phases": phases,
            "params": params
        }

    # Binding controlled connections
    for conn in root.findall("connection"):
        tl_id = conn.get("tl")
        if tl_id and tl_id in tls_data:
            link_index = conn.get("linkIndex")
            if link_index is not None:
                idx = int(link_index)
                if "connections" not in tls_data[tl_id]:
                    tls_data[tl_id]["connections"] = {}

                tls_data[tl_id]["connections"][idx] = {
                    "from": conn.get("from"),
                    "to": conn.get("to"),
                    "dir": conn.get("dir")
                }

    return tls_data, tls_nodes