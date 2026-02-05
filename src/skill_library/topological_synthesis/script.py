import subprocess
import xml.etree.ElementTree as ET
import os
import sys
from  src.language import t
import streamlit as st
sumo_bin = None
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
    sumo_bin = os.path.join(os.environ['SUMO_HOME'], 'bin')

def run(node_coords, adj_matrix, output_filename="network.net.xml", keep_temp_files=False,
                            edge_names=None, tls_config=None):
    """
    [Skill 1: Topological Synthesis]
    Transforms validated topological tensors into a SUMO-compliant .net.xml file.
    Corresponds to: Entity Instantiation & Topology Connection phase in Algorithm 3.
    """
    if not sumo_bin:
        st.error(t("err_sumo_home_short"))
        return False

    n = len(node_coords)
    if n == 0:
        st.warning(t("warn_empty_nodes"))
        return False

    # 1. Entity Instantiation: Initialize XML structures for nodes
    nodes_data = []
    for i, (x, y) in enumerate(node_coords):
        nodes_data.append({"id": str(i), "x": f"{float(x):.6f}", "y": f"{float(y):.6f}"})

    # 2. Topology Connection: Serialize edge dependencies from the adjacency matrix
    edges_data = []
    for i in range(n):
        for j in range(n):
            if i == j: continue
            props = adj_matrix[i][j]
            if props and isinstance(props, (list, tuple)) and len(props) == 2:
                speed, lanes = props
                e_id = f"E_{i}_to_{j}"
                if edge_names and (i, j) in edge_names:
                    e_id = edge_names[(i, j)]
                edges_data.append({
                    "id": e_id, "from": str(i), "to": str(j),
                    "speed": str(speed), "numLanes": str(lanes)
                })

    if not edges_data:
        st.warning(t("warn_no_edges"))
        return False

    # 3. Artifact Compilation: Write intermediate XML for netconvert
    nod_xml_file = "temp_nodes.nod.xml"
    edg_xml_file = "temp_edges.edg.xml"

    root_n = ET.Element('nodes')
    for nd in nodes_data: ET.SubElement(root_n, 'node', nd)
    ET.ElementTree(root_n).write(nod_xml_file, encoding='utf-8')

    root_e = ET.Element('edges')
    for ed in edges_data: ET.SubElement(root_e, 'edge', ed)
    ET.ElementTree(root_e).write(edg_xml_file, encoding='utf-8')

    # 4. Orchestrate netconvert for deterministic graph mapping
    tls_type = tls_config.get("type", "actuated") if tls_config else "actuated"
    tls_cycle = str(tls_config.get("cycle", 90)) if tls_config else "90"

    netconvert_cmd = [
        os.path.join(sumo_bin, "netconvert"),
        "--node-files", nod_xml_file,
        "--edge-files", edg_xml_file,
        "--output-file", output_filename,
        "--tls.guess", "true",
        "--tls.guess.threshold", "3",
        "--tls.default-type", tls_type,
        "--tls.cycle.time", tls_cycle,
        "--no-turnarounds", "true",
        "--no-turnarounds.except-deadend", "false",
        "--offset.disable-normalization", "true",
        "--default.speed", "13.9",
        "--default.lanenumber", "1",
        "--default.lanewidth", "3.2",
        "--roundabouts.guess", "true",
        "--output.street-names", "true"
    ]

    try:
        subprocess.run(netconvert_cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        st.error(t("err_netconvert", e=e.stderr))
        return False
    finally:
        if not keep_temp_files:
            if os.path.exists(nod_xml_file): os.remove(nod_xml_file)
            if os.path.exists(edg_xml_file): os.remove(edg_xml_file)