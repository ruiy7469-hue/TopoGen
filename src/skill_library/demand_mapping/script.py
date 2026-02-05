import random
import sumolib


def run(net_file, traffic_config_list, vtype_params=None, generate_detectors=True):
    """
    [Skill: Demand Synthesis]
    Maps high-level traffic demand-mapping matrices into discrete trip artifacts (.rou.xml).
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