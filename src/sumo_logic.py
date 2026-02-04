"""
TopoGen: Acting Layer (The Hands)
This module implements the Skill-Based Execution system as defined in Algorithm 3.
It contains a library of pre-verified functional primitives (Skills) that the
controller orchestrates based on the reasoned topological graph (GIR).
"""

import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import streamlit as st
import matplotlib.pyplot as plt
import random
from src.language import t

# --- TopoGen Skill Registry (Algorithm 3 Metadata) ---
SKILLS_MANIFEST = {
    "Network_Synthesis": {
        "description": "Transforms GIR JSON into SUMO .net.xml artifacts.",
        "parameters": ["node_coords", "adj_matrix"],
        "pre_condition": "Topological graph must be validated and consistent."
    },
    "Traffic_Demand_Mapping": {
        "description": "Converts demand matrices into executable .rou.xml files.",
        "parameters": ["net_file", "flow_list"],
        "pre_condition": "Network file must exist."
    },
    "Execution_Orchestration": {
        "description": "Launches the SUMO-GUI with orchestrated configuration.",
        "parameters": ["net_file", "rou_file", "add_file"],
        "pre_condition": "All XML artifacts must be compiled."
    }
}

# Environment configuration for SUMO binaries
sumo_bin = None
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
    sumo_bin = os.path.join(os.environ['SUMO_HOME'], 'bin')


class TopoGenSkillLibrary:
    """
    Skill Library S = {s1, s2, ..., sM}
    Each method represents a verified 'Skill' that the agent can orchestrate.
    """

    @staticmethod
    def skill_network_synthesis(node_coords, adj_matrix, output_filename="network.net.xml", keep_temp_files=False,
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

    @staticmethod
    def skill_temporal_logic_serialization(tls_data, filename="tls.add.xml"):
        """
        [Skill: Temporal Logic Serialization]
        Converts structured TLS data into SUMO additional artifacts.
        """
        root = ET.Element('additional')
        for tl_id, data in tls_data.items():
            tl_attrs = {
                "id": tl_id,
                "type": data["type"],
                "programID": "0",
                "offset": str(data["offset"])
            }
            tl_tag = ET.SubElement(root, "tlLogic", tl_attrs)

            if "params" in data:
                for k, v in data["params"].items():
                    ET.SubElement(tl_tag, "param", {"key": k, "value": str(v)})

            for ph in data["phases"]:
                ph_attrs = {"duration": str(ph["duration"]), "state": ph["state"]}
                if data["type"] == "actuated":
                    ph_attrs["minDur"] = str(ph.get("minDur", ph["duration"]))
                    ph_attrs["maxDur"] = str(ph.get("maxDur", ph["duration"]))
                ET.SubElement(tl_tag, "phase", ph_attrs)

        ET.ElementTree(root).write(filename, encoding='utf-8')
        return filename

    @staticmethod
    def skill_demand_mapping(net_file, traffic_config_list, vtype_params=None, generate_detectors=True):
        """
        [Skill: Demand Synthesis]
        Maps high-level traffic demand matrices into discrete trip artifacts (.rou.xml).
        """
        try:
            import sumolib
        except ImportError:
            return None, None

        net = sumolib.net.readNet(net_file)

        # Automatic sensor deployment (Skill within Demand Mapping)
        add_file = None
        if generate_detectors:
            add_file = "detectors.add.xml"
            with open(add_file, "w") as f:
                f.write('<additional>\n')
                for edge in net.getEdges():
                    if not edge.getID().startswith(":"):
                        for lane in edge.getLanes():
                            f.write(
                                f'    <inductionLoop id="det_{lane.getID()}" lane="{lane.getID()}" pos="-10" freq="60" file="det_out.xml"/>\n')
                f.write('</additional>\n')

        # Kinematic and Behavioral Parametrization
        default_vtypes = {
            "passenger": {"length": 5.0, "maxSpeed": 50.0, "accel": 2.6, "decel": 4.5, "guiShape": "passenger"},
            "truck": {"length": 7.0, "maxSpeed": 30.0, "accel": 1.5, "decel": 3.0, "guiShape": "truck"},
            "bus": {"length": 12.0, "maxSpeed": 25.0, "accel": 1.2, "decel": 2.5, "guiShape": "bus"},
            "motorcycle": {"length": 2.5, "maxSpeed": 55.0, "accel": 5.0, "decel": 6.0, "guiShape": "motorcycle"}
        }

        if vtype_params:
            for k, v in vtype_params.items():
                if k in default_vtypes: default_vtypes[k].update(v)

        rou_file = "traffic.rou.xml"
        all_trips = []
        veh_idx = 0

        for flow in traffic_config_list:
            src_edge, dst_edge = flow["src"], flow["dst"]
            count = int(flow["count"])
            t_start, t_end = float(flow.get("start_time", 0)), float(flow.get("end_time", 3600))
            ratios = flow.get("ratios", {"passenger": 1.0})

            duration = max(1, t_end - t_start)
            for _ in range(count):
                v_type = random.choices(list(ratios.keys()), weights=list(ratios.values()), k=1)[0]
                depart = t_start + random.uniform(0, duration)
                all_trips.append(
                    {"id": f"v{veh_idx}", "depart": depart, "src": src_edge, "dst": dst_edge, "type": v_type})
                veh_idx += 1

        all_trips.sort(key=lambda x: x["depart"])

        with open(rou_file, "w") as f:
            f.write('<routes>\n')
            for type_id, p in default_vtypes.items():
                attr_str = "".join([f' {k}="{v}"' for k, v in p.items()])
                f.write(f'    <vType id="{type_id}"{attr_str}/>\n')
            for t_v in all_trips:
                f.write(
                    f'    <trip id="{t_v["id"]}" type="{t_v["type"]}" depart="{t_v["depart"]:.2f}" from="{t_v["src"]}" to="{t_v["dst"]}" />\n')
            f.write('</routes>\n')

        return rou_file, add_file

    @staticmethod
    def skill_simulation_orchestration(net_file, route_file=None, add_file=None, delay=0):
        """
        [Skill: Simulation Orchestration]
        Launches the SUMO-GUI environment with validated configuration artifacts.
        """
        if not os.path.exists(net_file):
            st.error(t("err_net_not_found", file=net_file))
            return

        config_file = f"{os.path.splitext(net_file)[0]}.sumocfg"
        root = ET.Element('configuration')
        input_tag = ET.SubElement(root, 'input')
        ET.SubElement(input_tag, 'net-file', {'value': net_file})
        if route_file: ET.SubElement(input_tag, 'route-files', {'value': route_file})
        if add_file: ET.SubElement(input_tag, 'additional-files', {'value': add_file})

        # Processing presets for robust execution
        proc_tag = ET.SubElement(root, 'processing')
        ET.SubElement(proc_tag, 'ignore-route-errors', {'value': 'true'})
        ET.SubElement(proc_tag, 'collision.action', {'value': 'warn'})

        ET.ElementTree(root).write(config_file)

        # Skill internally invokes helper
        view_file = create_view_settings()

        cmd = [
            os.path.join(sumo_bin, "sumo-gui"), "-c", config_file, "--start",
            "--delay", str(delay), "--gui-settings-file", view_file
        ]
        try:
            subprocess.Popen(cmd)
            st.success(t("success_gui_start", delay=delay))
        except Exception as e:
            st.error(t("err_gui_start", e=e))

    @staticmethod
    def skill_metadata_ingestion(net_file):
        """Skill: Metadata Ingestion. Extracts topological metadata from physical XML artifacts."""
        return extract_tls_from_net(net_file)


# ==========================================
# Visualization & Intent Grounding Tools
# (Non-skill utility functions)
# ==========================================
def plot_network_with_edges(node_coords, adj_matrix):
    """
    Skill: GIR Visualization
    Renders the internal Graph-based Intermediate Representation for human-in-the-loop auditing.
    """
    fig, ax = plt.subplots(figsize=(7, 7))
    xs = [c[0] for c in node_coords]
    ys = [c[1] for c in node_coords]

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    x_range = x_max - x_min if x_max != x_min else 100
    y_range = y_max - y_min if y_max != y_min else 100

    ax.set_xlim(x_min - 0.1 * x_range, x_max + 0.1 * x_range)
    ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

    # Plot symbolic nodes
    for i, (x, y) in enumerate(node_coords):
        ax.plot(x, y, 'o', markersize=12, color='lightgray', zorder=1)
        ax.text(x, y, str(i), fontsize=10, color='black', ha='center', va='center', zorder=2)

    # Plot directed edges with offsets to prevent overlap
    n = len(node_coords)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            if adj_matrix[i][j]:
                x1, y1 = node_coords[i]
                x2, y2 = node_coords[j]

                dx, dy = x2 - x1, y2 - y1
                length = (dx ** 2 + dy ** 2) ** 0.5
                if length == 0: continue

                off_x = -dy / length * 2.0
                off_y = dx / length * 2.0

                sx, sy = x1 + off_x, y1 + off_y
                ex, ey = x2 + off_x, y2 + off_y

                ax.annotate("", xy=(ex, ey), xytext=(sx, sy),
                            arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.5), zorder=5)

    ax.text(0.02, 0.98, t("plot_naming_ex"), transform=ax.transAxes,
            fontsize=10, color='blue', verticalalignment='top',
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))

    ax.set_aspect('equal')
    ax.set_title(t("plot_net_preview"))
    ax.axis('off')
    plt.tight_layout()
    return fig


def plot_network_with_tls(node_coords, adj_matrix, tls_nodes=None):
    """
    Skill: Signalized Layout Visualization
    Highlights identified Traffic Light System (TLS) nodes for spatial auditing.
    """
    fig, ax = plt.subplots(figsize=(7, 7))

    for i, (x, y) in enumerate(node_coords):
        color = 'lightgray'
        marker = 'o'
        size = 8
        label_color = 'gray'

        # Highlight nodes identified as signalized junctions (Degree >= 3)
        if tls_nodes and str(i) in tls_nodes:
            color = 'red'
            marker = 's'
            size = 12
            label_color = 'darkred'

        ax.plot(x, y, marker=marker, markersize=size, color=color, zorder=1)
        ax.text(x, y, str(i), fontsize=9, color=label_color, ha='center', va='center', zorder=2, fontweight='bold')

    # Draw topological edges
    n = len(node_coords)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            if adj_matrix[i][j]:
                x1, y1 = node_coords[i]
                x2, y2 = node_coords[j]
                dx, dy = x2 - x1, y2 - y1
                length = (dx ** 2 + dy ** 2) ** 0.5
                if length == 0: continue
                off_x = -dy / length * 2.0
                off_y = dx / length * 2.0
                sx, sy = x1 + off_x, y1 + off_y
                ex, ey = x2 + off_x, y2 + off_y
                ax.annotate("", xy=(ex, ey), xytext=(sx, sy),
                            arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.5), zorder=5)

    ax.set_aspect('equal')
    ax.set_title(t("plot_net_tls"))
    ax.axis('off')
    return fig


def extract_tls_from_net(net_file):
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
def create_view_settings(filename="view.settings.xml"):
    """Generates standard rendering configurations for the Simulation GUI."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<viewsettings>
    <scheme name="real world"/>
    <delay value="0"/>
    <viewport zoom="100" x="0" y="0"/>
</viewsettings>"""
    with open(filename, "w") as f:
        f.write(content)
    return filename