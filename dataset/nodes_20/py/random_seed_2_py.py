import os
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

def create_sumo_network(node_coords, adj_matrix, output_filename="random_seed_2.net.xml", keep_temp_files=False, edge_names=None, tls_config=None):
    if not sumo_bin:
        print("❌ Error: SUMO_HOME not found.")
        return False

    n = len(node_coords)
    if n == 0:
        print("⚠️ Warning: Empty nodes.")
        return False

    nodes_data = []
    for i, (x, y) in enumerate(node_coords):
        nodes_data.append({"id": str(i), "x": f"{float(x):.6f}", "y": f"{float(y):.6f}"} )

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
        print(f"✅ Successfully generated: {output_filename}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Netconvert failed: {e.stderr}")
        return False
    finally:
        if not keep_temp_files:
            if os.path.exists(nod_xml_file): os.remove(nod_xml_file)
            if os.path.exists(edg_xml_file): os.remove(edg_xml_file)

if __name__ == "__main__":
    null = None
    node_coordinates = [
        [0, 300],
        [0, 500],
        [600, 500],
        [300, 200],
        [100, 300],
        [600, 0],
        [200, 500],
        [200, 200],
        [500, 300],
        [100, 600],
        [500, 500],
        [0, 200],
        [600, 200],
        [300, 600],
        [300, 400],
        [400, 400],
        [600, 300],
        [400, 0],
        [500, 600],
        [100, 100]
    ]

    adjacency_matrix = [
        [null, [13.9, 1], null, null, [13.9, 1], null, null, null, null, null, [13.9, 1], [13.9, 1], null, null, null, null, null, null, null, null],
        [[13.9, 1], null, null, null, null, null, null, null, null, [13.9, 1], null, null, null, null, null, null, null, null, null, null],
        [null, null, null, null, null, null, null, null, null, null, [13.9, 1], null, null, null, null, null, null, null, [13.9, 1], null],
        [null, null, null, null, null, null, null, [13.9, 1], null, null, null, null, null, null, [13.9, 1], null, null, [13.9, 1], null, null],
        [[13.9, 1], null, null, null, null, null, null, [13.9, 1], null, null, null, [13.9, 1], null, null, null, null, null, null, null, null],
        [null, null, null, null, null, null, null, null, null, null, null, null, [13.9, 1], null, null, null, null, [13.9, 1], null, null],
        [null, null, null, null, null, null, null, null, null, [13.9, 1], null, null, null, [13.9, 1], [13.9, 1], null, null, null, null, null],
        [null, null, null, [13.9, 1], [13.9, 1], null, null, null, null, null, null, null, null, null, null, null, null, null, null, [13.9, 1]],
        [null, null, null, null, null, null, null, null, null, null, null, null, [13.9, 1], null, null, [13.9, 1], [13.9, 1], null, null, null],
        [null, [13.9, 1], null, null, null, null, [13.9, 1], null, null, null, null, null, null, [13.9, 1], null, null, null, null, null, null],
        [[13.9, 1], null, [13.9, 1], null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, [13.9, 1], null],
        [[13.9, 1], null, null, null, [13.9, 1], null, null, null, null, null, null, null, null, null, null, null, null, null, null, [13.9, 1]],
        [null, null, null, null, null, [13.9, 1], null, null, [13.9, 1], null, null, null, null, null, null, null, [13.9, 1], null, null, null],
        [null, null, null, null, null, null, [13.9, 1], null, null, [13.9, 1], null, null, null, null, null, null, null, null, null, null],
        [null, null, null, [13.9, 1], null, null, [13.9, 1], null, null, null, null, null, null, null, null, [13.9, 1], null, null, null, null],
        [null, null, null, null, null, null, null, null, [13.9, 1], null, null, null, null, null, [13.9, 1], null, null, null, null, null],
        [null, null, null, null, null, null, null, null, [13.9, 1], null, null, null, [13.9, 1], null, null, null, null, null, null, null],
        [null, null, null, [13.9, 1], null, [13.9, 1], null, null, null, null, null, null, null, null, null, null, null, null, null, null],
        [null, null, [13.9, 1], null, null, null, null, null, null, null, [13.9, 1], null, null, null, null, null, null, null, null, null],
        [null, null, null, null, null, null, null, [13.9, 1], null, null, null, [13.9, 1], null, null, null, null, null, null, null, null],
    ]

    create_sumo_network(node_coordinates, adjacency_matrix, output_filename="random_seed_2.net.xml")
