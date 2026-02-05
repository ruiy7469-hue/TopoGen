import xml.etree.ElementTree as ET

def run(tls_data, filename="tls.add.xml"):
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