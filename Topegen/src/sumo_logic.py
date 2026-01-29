import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import streamlit as st
import matplotlib.pyplot as plt
import random
def create_sumo_network(node_coords, adj_matrix, output_filename="network.net.xml", keep_temp_files=False,
                        edge_names=None, tls_config=None):
    """根据节点坐标和邻接矩阵创建 SUMO 路网（支持有向连接）"""
    if not sumo_bin:
        st.error(t("err_sumo_home_short"))
        return False

    n = len(node_coords)
    if n == 0:
        st.warning(t("warn_empty_nodes"))
        return False

    nodes_data = []
    for i, (x, y) in enumerate(node_coords):
        nodes_data.append({"id": str(i), "x": f"{float(x):.6f}", "y": f"{float(y):.6f}"})

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
        "--tls.guess.threshold", "3",  # 三岔口也加信号灯
        "--tls.default-type", tls_type,  # 信号灯类型
        "--tls.cycle.time", tls_cycle,  # 周期
        "--no-turnarounds", "true",
        "--no-turnarounds.except-deadend", "false",
        "--offset.disable-normalization", "true",  # 保持原始坐标
        "--default.speed", "13.9",  # 默认速度 ~50km/h
        "--default.lanenumber", "1",  # 默认车道数
        "--default.lanewidth", "3.2",  # 标准车道宽
        "--roundabouts.guess", "true",  # 自动识别环岛
        "--output.street-names", "true"  # GUI 显示名称
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


# ==========================================
# Part 1.5: 可视化与流量生成逻辑 (新)
# ==========================================
def plot_network_with_edges(node_coords, adj_matrix):
    """绘制路网，重点标注 Edge ID"""
    fig, ax = plt.subplots(figsize=(7, 7))
    xs = [c[0] for c in node_coords]
    ys = [c[1] for c in node_coords]

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    x_range = x_max - x_min if x_max != x_min else 100
    y_range = y_max - y_min if y_max != y_min else 100

    # 为顶部留出约 20% 的空间放说明文字，四周留出 10% 避免压线
    ax.set_xlim(x_min - 0.1 * x_range, x_max + 0.1 * x_range)
    ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

    # 1. 绘制节点 (淡一点，作为背景)
    for i, (x, y) in enumerate(node_coords):
        ax.plot(x, y, 'o', markersize=12, color='lightgray', zorder=1)
        ax.text(x, y, str(i), fontsize=10, color='black', ha='center', va='center', zorder=2)

    # 2. 绘制边并标注 ID
    n = len(node_coords)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            if adj_matrix[i][j]:
                x1, y1 = node_coords[i]
                x2, y2 = node_coords[j]

                # 计算偏移量 (防止双向车道重叠)
                # 向量 (dx, dy)
                dx, dy = x2 - x1, y2 - y1
                length = (dx ** 2 + dy ** 2) ** 0.5
                if length == 0: continue

                # 单位法向量 (用于横向偏移)
                off_x = -dy / length * 2.0  # 偏移距离 2米
                off_y = dx / length * 2.0

                # 新的起点和终点 (偏移后)
                sx, sy = x1 + off_x, y1 + off_y
                ex, ey = x2 + off_x, y2 + off_y

                # 画箭头线
                ax.annotate("", xy=(ex, ey), xytext=(sx, sy),
                            arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.5), zorder=5)

                # 在中点标注 Edge ID
                mid_x, mid_y = (sx + ex) / 2, (sy + ey) / 2
                edge_id = f"E_{i}_to_{j}"

                # 添加文字背景框，防止看不清
                # ax.text(mid_x, mid_y, edge_id, ...) # 已移除，按需求不显示具体名称

    # 添加命名示例
    ax.text(0.02, 0.98, t("plot_naming_ex"), transform=ax.transAxes,
            fontsize=10, color='blue', verticalalignment='top',
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))

    ax.set_aspect('equal')
    ax.set_title(t("plot_net_preview"))
    ax.axis('off')
    plt.tight_layout()
    return fig


def plot_network_with_tls(node_coords, adj_matrix, tls_nodes=None):
    """绘制路网，并高亮显示信号灯节点"""
    fig, ax = plt.subplots(figsize=(7, 7))

    # 1. 绘制节点
    for i, (x, y) in enumerate(node_coords):
        # 默认样式
        color = 'lightgray'
        marker = 'o'
        size = 8
        label_color = 'gray'

        # 如果是 TLS 节点，特殊标记
        if tls_nodes and str(i) in tls_nodes:
            color = 'red'
            marker = 's'  # square
            size = 12
            label_color = 'darkred'

        ax.plot(x, y, marker=marker, markersize=size, color=color, zorder=1)
        ax.text(x, y, str(i), fontsize=9, color=label_color, ha='center', va='center', zorder=2, fontweight='bold')

    # 2. 绘制边 (同上)
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
    """从 .net.xml 中提取 TLS 逻辑和相位信息"""
    if not os.path.exists(net_file):
        return {}, {}

    tree = ET.parse(net_file)
    root = tree.getroot()

    # 1. 找出哪些节点是 TLS
    # <junction id="1" type="traffic_light" ...>
    tls_nodes = {}  # {node_id: tls_id}
    for junc in root.findall("junction"):
        if junc.get("type") == "traffic_light":
            # 注意: 有些 junction 可能共享同一个 tlLogic (joined tls)
            tl_id = junc.get("tl")
            node_id = junc.get("id")
            tls_nodes[node_id] = tl_id

    # 2. 提取 TLS 逻辑
    # <tlLogic id="J1" type="actuated" programID="0" offset="0">
    #    <phase duration="42" state="GrGr"/>
    # </tlLogic>
    tls_data = {}
    for tl in root.findall("tlLogic"):
        tl_id = tl.get("id")
        # 只提取 programID="0" 的 (默认程序)
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
            "cycle": 0,  # 稍后计算
            "offset": float(tl.get("offset", 0)),
            "phases": phases,
            "params": params
        }
        # 计算总周期
        total_cycle = sum(p["duration"] for p in phases)
        tls_data[tl_id]["cycle"] = total_cycle

    # 3. 提取 Connection 信息 (用于映射 State 字符串)
    # <connection from="E1" to="E2" tl="J1" linkIndex="0" dir="s" .../>
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


def generate_tls_add_file(tls_data, filename="tls.add.xml"):
    """生成包含修改后 TLS 逻辑的 additional 文件"""
    root = ET.Element('additional')

    for tl_id, data in tls_data.items():
        # <tlLogic ...>
        tl_attrs = {
            "id": tl_id,
            "type": data["type"],
            "programID": "0",  # 覆盖默认程序
            "offset": str(data["offset"])
        }
        tl_tag = ET.SubElement(root, "tlLogic", tl_attrs)

        # 写入参数 (如 max-gap)
        if "params" in data:
            for k, v in data["params"].items():
                ET.SubElement(tl_tag, "param", {"key": k, "value": str(v)})

        for ph in data["phases"]:
            ph_attrs = {
                "duration": str(ph["duration"]),
                "state": ph["state"]
            }
            # 只有 actuated 类型才写入 minDur/maxDur，或者如果它们与 duration 不同
            if data["type"] == "actuated":
                ph_attrs["minDur"] = str(ph.get("minDur", ph["duration"]))
                ph_attrs["maxDur"] = str(ph.get("maxDur", ph["duration"]))

            ET.SubElement(tl_tag, "phase", ph_attrs)

    ET.ElementTree(root).write(filename, encoding='utf-8')
    return filename


def generate_traffic_by_edges(net_file, traffic_config_list, vtype_params=None, generate_detectors=True):
    """
    直接使用 Edge ID 生成流量
    traffic_config_list: [{"src":..., "dst":..., "count":..., "start_time":..., "end_time":..., "ratios": {...}}]
    vtype_params: {"car": {...}, "truck": {...}}
    """
    try:
        import sumolib
    except ImportError:
        return None, None

    net = sumolib.net.readNet(net_file)
    edges = [e.getID() for e in net.getEdges() if not e.getID().startswith(":")]

    # 1. 检测器 (修改这部分逻辑)
    add_file = None  # 默认为 None
    if generate_detectors:  # <--- 只有开关开启时才生成文件
        add_file = "detectors.add.xml"
        with open(add_file, "w") as f:
            f.write('<additional>\n')
            for edge_id in edges:
                edge = net.getEdge(edge_id)
                for lane in edge.getLanes():
                    f.write(
                        f'    <inductionLoop id="det_{lane.getID()}" lane="{lane.getID()}" pos="-10" freq="60" file="det_out.xml"/>\n')
            f.write('</additional>\n')

    # 2. 流量
    rou_file = "traffic.rou.xml"
    all_trips = []
    veh_idx = 0

    # 默认车型参数
    default_vtypes = {
        "passenger": {"length": 5.0, "maxSpeed": 50.0, "accel": 2.6, "decel": 4.5, "color": "1,0.8,0",
                      "guiShape": "passenger"},
        "truck": {"length": 7.0, "maxSpeed": 30.0, "accel": 1.5, "decel": 3.0, "color": "0,1,0", "guiShape": "truck"},
        "bus": {"length": 12.0, "maxSpeed": 25.0, "accel": 1.2, "decel": 2.5, "color": "0,0,1", "guiShape": "bus"},
        "motorcycle": {"length": 2.5, "maxSpeed": 55.0, "accel": 5.0, "decel": 6.0, "color": "0.8,0,0.8",
                       "guiShape": "motorcycle"}
    }

    if vtype_params:
        # 合并用户参数
        for k, v in vtype_params.items():
            if k in default_vtypes:
                default_vtypes[k].update(v)

    for flow in traffic_config_list:
        src_edge = flow["src"]
        dst_edge = flow["dst"]
        count = int(flow["count"])
        t_start = float(flow.get("start_time", 0))
        t_end = float(flow.get("end_time", 3600))
        ratios = flow.get("ratios", {"passenger": 1.0})  # e.g. {"passenger": 0.8, "truck": 0.2}

        # 准备车型权重
        types = list(ratios.keys())
        weights = list(ratios.values())

        duration = t_end - t_start
        if duration <= 0: duration = 1

        for i in range(count):
            # 随机选择车型
            v_type = random.choices(types, weights=weights, k=1)[0]

            # 随机出发时间
            depart = t_start + random.uniform(0, duration)

            all_trips.append({
                "id": f"v{veh_idx}",
                "depart": depart,
                "src": src_edge,
                "dst": dst_edge,
                "type": v_type
            })
            veh_idx += 1

    all_trips.sort(key=lambda x: x["depart"])

    with open(rou_file, "w") as f:
        f.write('<routes>\n')

        # 写入 vType 定义
        for type_id, p in default_vtypes.items():
            # 构建属性字符串
            attr_str = ""
            for k, v in p.items():
                attr_str += f' {k}="{v}"'
            f.write(f'    <vType id="{type_id}"{attr_str}/>\n')

        for t in all_trips:
            f.write(
                f'    <trip id="{t["id"]}" type="{t["type"]}" depart="{t["depart"]:.2f}" from="{t["src"]}" to="{t["dst"]}" />\n')
        f.write('</routes>\n')

    return rou_file, add_file

def create_view_settings(filename="view.settings.xml"):
    """创建 SUMO-GUI 视图配置文件，强制显示车辆形状"""
    content = """<viewsettings>
    <scheme name="real world"/>
    <delay value="0"/>
    <viewport zoom="100" x="0" y="0"/>
    <snapshot-file value=""/>
</viewsettings>"""
    with open(filename, "w") as f:
        f.write(content)
    return filename


def open_in_sumo_gui(net_file, route_file=None, add_file=None, delay=0):
    """生成 .sumocfg 并启动 SUMO-GUI"""
    if not os.path.exists(net_file):
        st.error(t("err_net_not_found", file=net_file))
        return

    config_file = f"{os.path.splitext(net_file)[0]}.sumocfg"
    root = ET.Element('configuration')
    input_tag = ET.SubElement(root, 'input')
    ET.SubElement(input_tag, 'net-file', {'value': net_file})

    if route_file:
        ET.SubElement(input_tag, 'route-files', {'value': route_file})
    if add_file:
        ET.SubElement(input_tag, 'additional-files', {'value': add_file})

    time_tag = ET.SubElement(root, 'time')
    ET.SubElement(time_tag, 'begin', {'value': '0'})

    # 容错设置
    proc_tag = ET.SubElement(root, 'processing')
    ET.SubElement(proc_tag, 'ignore-route-errors', {'value': 'true'})
    ET.SubElement(proc_tag, 'collision.action', {'value': 'warn'})

    ET.ElementTree(root).write(config_file)

    # 生成视图配置
    view_file = create_view_settings()

    cmd = [
        os.path.join(sumo_bin, "sumo-gui"),
        "-c", config_file,
        "--start",
        "--ignore-route-errors",
        "--collision.action", "warn",
        "--delay", str(delay),
        "--gui-settings-file", view_file
    ]
    try:
        subprocess.Popen(cmd)
        st.success(t("success_gui_start", delay=delay))
    except Exception as e:
        st.error(t("err_gui_start", e=e))