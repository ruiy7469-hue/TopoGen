import subprocess
import os
import sys
import xml.etree.ElementTree as ET
from  src.language import t
import streamlit as st
sumo_bin = None
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
    sumo_bin = os.path.join(os.environ['SUMO_HOME'], 'bin')

def run(net_file, route_file=None, add_file=None, delay=0):
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