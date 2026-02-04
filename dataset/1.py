import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import random
import math
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sumo_bin = None
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
    sumo_bin = os.path.join(os.environ['SUMO_HOME'], 'bin')


def run_netconvert(node_coords, adj_matrix, output_path):
    if not sumo_bin:
        return False

    n = len(node_coords)
    temp_dir = os.path.dirname(output_path)
    nod_xml = os.path.join(temp_dir, "temp.nod.xml")
    edg_xml = os.path.join(temp_dir, "temp.edg.xml")
    root_n = ET.Element('nodes')
    for i, (x, y) in enumerate(node_coords):
        ET.SubElement(root_n, 'node', {"id": str(i), "x": f"{x:.2f}", "y": f"{y:.2f}"})
    ET.ElementTree(root_n).write(nod_xml)
    root_e = ET.Element('edges')
    for i in range(n):
        for j in range(n):
            props = adj_matrix[i][j]
            if props and isinstance(props, list):
                ET.SubElement(root_e, 'edge', {
                    "id": f"E_{i}_to_{j}", "from": str(i), "to": str(j),
                    "speed": str(props[0]), "numLanes": str(props[1])
                })
    ET.ElementTree(root_e).write(edg_xml)
    cmd = [
        os.path.join(sumo_bin, "netconvert"),
        "--node-files", nod_xml,
        "--edge-files", edg_xml,
        "--output-file", output_path,
        "--tls.guess", "true",
        "--no-turnarounds", "true",
        "--offset.disable-normalization", "true"
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(nod_xml): os.remove(nod_xml)
        if os.path.exists(edg_xml): os.remove(edg_xml)
        return True
    except:
        return False



def generate_data(seed, n_nodes, base_output_dir,grid):
    # --- 1. 文件夹路径配置 ---
    sub_dirs = {
        "DS": os.path.join(base_output_dir, "Digital Schematics"),
        "NL": os.path.join(base_output_dir, "Natural Language"),
        "CM": os.path.join(base_output_dir, "Combined Modalities"),
        "MS": os.path.join(base_output_dir, "Manual Sketches"),
        "PY": os.path.join(base_output_dir, "py"),
        "XML": os.path.join(base_output_dir, "xml")
    }
    for path in sub_dirs.values():
        os.makedirs(path, exist_ok=True)

    random.seed(seed)
    np.random.seed(seed)

    grid_max = grid
    grid_range = range(0, grid_max, 100)
    possible_points = [(x, y) for x in grid_range for y in grid_range]

    selected_points = random.sample(possible_points, n_nodes)
    pos = {i: selected_points[i] for i in range(n_nodes)}
    pos_list = [list(pos[i]) for i in range(n_nodes)]  # 用于 XML 生成

    G = nx.Graph()
    G.add_nodes_from(range(n_nodes))
    for i in range(n_nodes):
        distances = []
        for j in range(n_nodes):
            if i != j:
                dist = math.dist(pos[i], pos[j])
                distances.append((j, dist))
        distances.sort(key=lambda x: x[1])
        for neighbor, dist in distances[:2]:
            if dist <= 450:
                G.add_edge(i, neighbor, weight=dist)

    if not nx.is_connected(G):
        components = list(nx.connected_components(G))
        for k in range(len(components) - 1):
            u = list(components[k])[0]
            min_dist, closest = float('inf'), -1
            for v in components[k + 1]:
                d = math.dist(pos[u], pos[v])
                if d < min_dist:
                    min_dist, closest = d, v
            G.add_edge(u, closest, weight=min_dist)

    # --- 3. 准备数据 ---
    coords_list_str = [f"{i}{pos[i]}" for i in range(n_nodes)]
    coords_tuple_str = [f"{pos[i]}" for i in range(n_nodes)]

    adj_matrix_py = [[None] * n_nodes for _ in range(n_nodes)]
    conn_desc_list = []

    for u in range(n_nodes):
        neighbors = list(G.neighbors(u))
        if not neighbors: continue
        for v in neighbors:
            adj_matrix_py[u][v] = [13.9, 1]
            adj_matrix_py[v][u] = [13.9, 1]

        targets = [str(n) for n in neighbors]
        target_str = ", ".join(targets[:-1]) + " and " + targets[-1] if len(targets) > 1 else targets[0]
        conn_desc_list.append(f"node {u} connects to node{'s' if len(targets) > 1 else ''} {target_str}")

    conn_desc_str = "; ".join(conn_desc_list) + "."

    # --- 4. 生成文件 ---

    # [1] Digital Schematics (PNG)
    fig_size = max(10, n_nodes)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=100)
    nx.draw_networkx_edges(G, pos, edge_color='black', width=2, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=700, node_color='#4169E1', edgecolors='black', ax=ax)
    nx.draw_networkx_labels(G, pos, font_color='white', font_size=12, font_weight='bold', ax=ax)
    edge_labels = {(u, v): f"{d['weight']:.0f}m" for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10,
                                 bbox=dict(boxstyle="round,pad=0.3", ec="none", fc="white", alpha=1), ax=ax)
    x_vals = [p[0] for p in pos.values()]
    y_vals = [p[1] for p in pos.values()]
    min_x, max_x, min_y = min(x_vals), max(x_vals), min(y_vals)
    scale_x, scale_y = min_x, min_y - 50
    ax.plot([scale_x, scale_x + 100], [scale_y, scale_y], color='black', linewidth=4)
    ax.text(scale_x + 50, scale_y - 20, '100m', ha='center', va='top', fontsize=12, fontweight='bold')
    pad = 80
    ax.set_xlim(min_x - pad, max_x + pad)
    ax.set_ylim(min_y - pad - 30, max(y_vals) + pad)
    ax.set_aspect('equal')
    plt.axis('off')
    ds_path = os.path.join(sub_dirs["DS"], f"random_seed_{seed}_DS.png")
    plt.savefig(ds_path, bbox_inches='tight')
    plt.close()

    # [2] Natural Language (TXT)
    nl_text = (
        f"The road network to be generated consists of {n_nodes} nodes with the following coordinates: "
        f"{', '.join(coords_list_str)}. "
        f"The topological connectivity is defined as follows: {conn_desc_str} "
        "All roads are bidirectional."
    )
    with open(os.path.join(sub_dirs["NL"], f"random_seed_{seed}_NL.txt"), 'w', encoding='utf-8') as f:
        f.write(nl_text)

    # [3] Combined Modalities (Folder)
    cm_seed_dir = os.path.join(sub_dirs["CM"], f"random_seed_{seed}")
    os.makedirs(cm_seed_dir, exist_ok=True)
    shutil.copy(ds_path, os.path.join(cm_seed_dir, f"random_seed_{seed}_CM.png"))
    cm_text = (
        "I want to generate a road network as shown in the figure. "
        "The node IDs and edge lengths are clearly labeled in the figure, and all roads are bidirectional. "
        f"The precise coordinates of the nodes corresponding to IDs 0 to {n_nodes - 1} are given as numerical tuples: "
        f"{', '.join(coords_tuple_str)}."
    )
    with open(os.path.join(cm_seed_dir, f"random_seed_{seed}_CM.txt"), 'w', encoding='utf-8') as f:
        f.write(cm_text)

    # [4] Python Script (PY) -> 这是一个 XML 生成器脚本

    # 构造数据字符串
    py_nodes_str = "[\n" + ",\n".join([f"        [{pos[i][0]}, {pos[i][1]}]" for i in range(n_nodes)]) + "\n    ]"
    py_matrix_str = "[\n"
    for row in adj_matrix_py:
        row_content = ", ".join([str(item) if item else "null" for item in row])
        py_matrix_str += f"        [{row_content}],\n"
    py_matrix_str += "    ]"

    # 目标 XML 文件名（用户下载脚本后运行时生成的）
    target_xml_name = f"random_seed_{seed}.net.xml"

    # 【核心部分】嵌入生成 XML 的模板代码
    # 注意：这里把 streamlit 去掉了，改成了 print，方便独立运行
    py_template = f"""import os
import sys
import subprocess
import xml.etree.ElementTree as ET

# 自动检测 SUMO 路径
sumo_bin = None
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
    sumo_bin = os.path.join(os.environ['SUMO_HOME'], 'bin')

def create_sumo_network(node_coords, adj_matrix, output_filename="{target_xml_name}", keep_temp_files=False, edge_names=None, tls_config=None):
    if not sumo_bin:
        print("❌ Error: SUMO_HOME not found.")
        return False

    n = len(node_coords)
    if n == 0:
        print("⚠️ Warning: Empty nodes.")
        return False

    nodes_data = []
    for i, (x, y) in enumerate(node_coords):
        nodes_data.append({{"id": str(i), "x": f"{{float(x):.6f}}", "y": f"{{float(y):.6f}}"}} )

    edges_data = []
    for i in range(n):
        for j in range(n):
            if i == j: continue
            props = adj_matrix[i][j]
            if props and isinstance(props, (list, tuple)) and len(props) == 2:
                speed, lanes = props
                e_id = f"E_{{i}}_to_{{j}}"
                if edge_names and (i, j) in edge_names:
                    e_id = edge_names[(i, j)]
                edges_data.append({{
                    "id": e_id, "from": str(i), "to": str(j),
                    "speed": str(speed), "numLanes": str(lanes)
                }})

    if not edges_data:
        print("⚠️ Warning: No edges.")
        return False

    nod_xml_file = "temp_nodes.nod.xml"
    edg_xml_file = "temp_edges.edg.xml"

    root_n = ET.Element('nodes')
    for nd in nodes_data: ET.SubElement(root_n, 'node', nd)
    ET.ElementTree(root_n).write(nod_xml_file, encoding='utf-8')

    root_e = ET.Element('edges')
    for ed in edges_data: ET.SubElement(root_e, 'edge', ed)
    ET.ElementTree(root_e).write(edg_xml_file, encoding='utf-8')

    # --- 调用 netconvert ---
    tls_type = "actuated"
    tls_cycle = "90"
    if tls_config:
        tls_type = tls_config.get("type", "actuated")
        tls_cycle = str(tls_config.get("cycle", 90))

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
        print(f"✅ Successfully generated: {{output_filename}}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Netconvert failed: {{e.stderr}}")
        return False
    finally:
        if not keep_temp_files:
            if os.path.exists(nod_xml_file): os.remove(nod_xml_file)
            if os.path.exists(edg_xml_file): os.remove(edg_xml_file)

if __name__ == "__main__":
    null = None
    node_coordinates = {py_nodes_str}

    adjacency_matrix = {py_matrix_str}

    create_sumo_network(node_coordinates, adjacency_matrix, output_filename="{target_xml_name}")
"""
    with open(os.path.join(sub_dirs["PY"], f"random_seed_{seed}_py.py"), 'w', encoding='utf-8') as f:
        f.write(py_template)

    # [5] SUMO XML (用于 Ground Truth 文件夹)
    xml_path = os.path.join(sub_dirs["XML"], f"random_seed_{seed}.net.xml")
    if run_netconvert(pos_list, adj_matrix_py, xml_path):
        print(f"✅ [Seed {seed}] 真值 XML 已生成")
    else:
        print(f"❌ [Seed {seed}] 真值 XML 生成失败")

    print(f"🎉 Seed {seed} finish\n")


# ==========================================
# 批量执行
# ==========================================
if __name__ == "__main__":

    OUTPUT_DIR = "nodes_10"
    SEEDS = [1, 2, 3,4,5]
    grid= 500
    NODES = 10

    print(f"🚀 start: {OUTPUT_DIR}")
    for s in SEEDS:
        generate_data(s, NODES, OUTPUT_DIR,grid)
    print("🏁 finish!")