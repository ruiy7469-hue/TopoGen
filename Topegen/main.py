import os
import sys
import matplotlib
import pandas
import streamlit as st
from language import t
from sumo_logic import *
from ai_logic import *

# 配置 matplotlib 支持中文显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
# 环境变量检查
sumo_bin = None
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)
    sumo_bin = os.path.join(os.environ['SUMO_HOME'], 'bin')
else:
    st.error(t("err_sumo_home"))
    st.stop()

def main():
    st.set_page_config(page_title="SUMO AI Designer", layout="wide")
    st.title(t("title"))

    # --- Session State 管理状态 ---
    if "step" not in st.session_state: st.session_state.step = 1
    if "net_data" not in st.session_state: st.session_state.net_data = None
    if "user_flows" not in st.session_state: st.session_state.user_flows = []
    if "chat_history" not in st.session_state: st.session_state.chat_history = []
    if "edge_custom_names" not in st.session_state: st.session_state.edge_custom_names = {}
    if "tls_config" not in st.session_state: st.session_state.tls_config = {"type": "actuated", "cycle": 90}
    if "tls_data" not in st.session_state: st.session_state.tls_data = {}  # 存储详细的 TLS 数据
    if "tls_nodes" not in st.session_state: st.session_state.tls_nodes = {}  # 存储 TLS 节点映射
    if "vtype_params" not in st.session_state: st.session_state.vtype_params = {}
    if "enable_ai_check" not in st.session_state: st.session_state.enable_ai_check = False
    if "ai_check_logs" not in st.session_state: st.session_state.ai_check_logs = []
    if "pending_selection" not in st.session_state: st.session_state.pending_selection = None
    if "pending_verify_failure" not in st.session_state: st.session_state.pending_verify_failure = None
    if "verification_messages" not in st.session_state: st.session_state.verification_messages = []

    with st.sidebar:
        st.header(t("settings"))

        # 语言选择
        lang_opt = st.selectbox("Language / 语言", ["中文", "English"])
        st.session_state.lang = "zh" if lang_opt == "中文" else "en"
        st.header(t("settings"))

        model_options = ["Gemini", "Qwen "]
        selected_model = st.selectbox(t("select_model"), model_options)

        st.session_state.selected_model = selected_model
        api_key = st.text_input(t("input_api_key", model=selected_model), type="password")
        st.session_state.api_key = api_key

        temp = st.slider(
            t("temp_label"),
            min_value=0.0,
            max_value=1.0,
            value=0.1,  # 默认值
            step=0.1,
            help=t("temp_help")
        )
        # 将选择的温度存入 session，方便后台调用
        st.session_state.temp = temp

        st.divider()  # 画一条分割线，好看一点
        st.session_state.enable_ai_check = st.checkbox(
            t("ai_check_label"),  # 使用翻译函数获取标题
            value=st.session_state.get("enable_ai_check", False),
            help=t("ai_check_help")  # 使用翻译函数获取帮助文字
        )

        # 如果启用AI自查，显示第二个API Key输入框
        api_key_ai2 = ""
        if st.session_state.enable_ai_check:
            label_ai2 = f"AI2 API Key ({selected_model})"

            # 创建第二个输入框
            api_key_ai2 = st.text_input(
                label_ai2,
                type="password",
                key="api_key_ai2_input"  # 这是一个唯一的指纹，防止程序搞混两个输入框
            )

            # 把这个 Key 存到 session 状态里，方便后面调用
            st.session_state.api_key_ai2 = api_key_ai2

        if st.button(t("reset")):
            # 1. 核心状态重置
            st.session_state.step = 1
            st.session_state.user_flows = []
            st.session_state.chat_history = []
            st.session_state.selected_model = "Gemini"  # 重置时回到 Gemini
            st.session_state.api_key = ""

            # 2. 清理路网相关数据
            st.session_state.net_data = None
            st.session_state.edge_custom_names = {}

            # 3. 清理信号灯相关数据 (关键修正)
            st.session_state.tls_config = {"type": "actuated", "cycle": 90}
            st.session_state.tls_data = {}
            st.session_state.tls_nodes = {}
            st.session_state.removed_tls_nodes = set()  # 必须清空，否则影响下一次生成

            # 4. 清理车辆参数
            st.session_state.vtype_params = {}

            # 5. 清理 AI 验证中间状态
            st.session_state.ai_check_logs = []
            st.session_state.pending_selection = None
            st.session_state.pending_verify_failure = None
            st.session_state.verification_messages = []

            # 刷新页面
            st.rerun()

    # --- 阶段 1: AI 生成路网 ---
    if st.session_state.step == 1:
        st.subheader(t("step1_title"))
        c1, c2 = st.columns([2, 1])
        with c1:
            desc = st.text_area(t("desc_label"), t("desc_default"))
        with c2:
            img = st.file_uploader(t("img_label"), type=["png", "jpg"])

        if st.button(t("gen_btn"), type="primary"):
            if not api_key:
                return st.warning(t("need_api"))

            with st.spinner(t("ai_parsing")):
                prompt = build_multimodal_prompt(desc, img is not None)
                res, history = call_google_ai_vision(api_key, prompt, img)

                if res and history:
                    # 如果启用AI自查
                    if st.session_state.enable_ai_check:
                        st.info("🔍 AI自查功能已启用,开始双AI交叉验证...")

                        # 调用双AI验证
                        final_coords, final_matrix, agreed, ai1_final, ai2_final, logs = ai_cross_verification(
                            api_key, api_key_ai2, prompt, res, img
                        )

                        # 保存日志文件路径
                        st.session_state.ai_check_logs = logs

                        # 显示保存的日志文件
                        if logs:
                            with st.expander("📝 查看对话日志文件"):
                                for log_file in logs:
                                    st.text(log_file)

                        # 如果达成一致
                        if agreed and final_coords and final_matrix:
                            st.session_state.net_data = {"coords": final_coords, "matrix": final_matrix}
                            st.session_state.chat_history = history
                            st.session_state.step = 2
                            st.rerun()
                        # 如果未达成一致,让用户选择
                        elif ai1_final and ai2_final:
                            st.warning("⚠️ 两个AI未能达成一致,请选择一个方案:")
                            st.session_state.pending_selection = {
                                "ai1": ai1_final,
                                "ai2": ai2_final,
                                "history": history
                            }
                            st.rerun()
                        else:
                            # 验证失败,保存失败信息让用户确认后使用AI1原始方案
                            coords, matrix = clean_and_parse_json(res)
                            if coords and matrix:
                                st.session_state.pending_verify_failure = {
                                    "coords": coords,
                                    "matrix": matrix,
                                    "history": history,
                                    "reason": "AI2未能提供有效的验证反馈或修正方案"
                                }
                                st.rerun()
                    else:
                        # 未启用AI自查,直接使用AI1结果
                        coords, matrix = clean_and_parse_json(res)
                        if coords and matrix:
                            st.session_state.net_data = {"coords": coords, "matrix": matrix}
                            st.session_state.chat_history = history
                            st.session_state.step = 2
                            st.rerun()

        # 显示验证过程消息历史
        if st.session_state.verification_messages:
            with st.expander("📋 验证过程记录", expanded=True):
                for msg_item in st.session_state.verification_messages:
                    msg_type = msg_item.get("type", "write")
                    msg_text = msg_item.get("msg", "")
                    if msg_type == "success":
                        st.success(msg_text)
                    elif msg_type == "warning":
                        st.warning(msg_text)
                    elif msg_type == "info":
                        st.info(msg_text)
                    else:
                        st.write(msg_text)

        # 如果有待确认的验证失败,显示失败信息和确认按钮
        if st.session_state.pending_verify_failure:
            st.divider()
            st.subheader(t("ai_verify_failed"))
            st.warning(t("ai_verify_failed_reason", reason=st.session_state.pending_verify_failure.get("reason", "")))
            st.info(t("ai_verify_using_ai1"))

            # 显示AI1方案预览
            failure_data = st.session_state.pending_verify_failure
            if failure_data.get("coords") and failure_data.get("matrix"):
                fig_preview = plot_network_with_edges(failure_data["coords"], failure_data["matrix"])
                st.pyplot(fig_preview)

            if st.button(t("ai_verify_continue_btn"), type="primary", key="verify_failure_continue"):
                st.session_state.net_data = {
                    "coords": failure_data["coords"],
                    "matrix": failure_data["matrix"]
                }
                st.session_state.chat_history = failure_data["history"]
                st.session_state.pending_verify_failure = None
                st.session_state.step = 2
                st.rerun()

        # 如果有待选择的方案,显示选择界面
        if st.session_state.pending_selection:
            st.divider()
            st.subheader("🔀 请选择一个AI方案")

            col1, col2 = st.columns(2)

            with col1:
                st.write("### 方案 A - AI1")
                try:
                    ai1_data = json.loads(st.session_state.pending_selection["ai1"])
                    coords1 = ai1_data.get("node_coordinates")
                    matrix1 = ai1_data.get("adjacency_matrix")
                    if coords1 and matrix1:
                        fig1 = plot_network_with_edges(coords1, matrix1)
                        st.pyplot(fig1)
                        if st.button("✅ 选择方案 A", key="select_a"):
                            st.session_state.net_data = {"coords": coords1, "matrix": matrix1}
                            st.session_state.chat_history = st.session_state.pending_selection["history"]
                            st.session_state.pending_selection = None
                            st.session_state.step = 2
                            st.rerun()
                except Exception as e:
                    st.error(f"解析AI1方案出错: {e}")

            with col2:
                st.write("### 方案 B - AI2")
                try:
                    ai2_data = json.loads(st.session_state.pending_selection["ai2"])
                    coords2 = ai2_data.get("node_coordinates")
                    matrix2 = ai2_data.get("adjacency_matrix")
                    if coords2 and matrix2:
                        fig2 = plot_network_with_edges(coords2, matrix2)
                        st.pyplot(fig2)
                        if st.button("✅ 选择方案 B", key="select_b"):
                            st.session_state.net_data = {"coords": coords2, "matrix": matrix2}
                            st.session_state.chat_history = st.session_state.pending_selection["history"]
                            st.session_state.pending_selection = None
                            st.session_state.step = 2
                            st.rerun()
                except Exception as e:
                    st.error(f"解析AI2方案出错: {e}")
    elif st.session_state.step == 2:
        st.subheader(t("step2_title"))

        coords = st.session_state.net_data["coords"]
        matrix = st.session_state.net_data["matrix"]

        c_vis, c_fix = st.columns([1, 1])

        with c_vis:
            st.write(t("net_preview"))
            fig = plot_network_with_edges(coords, matrix)
            st.pyplot(fig)
            st.caption(t("current_turns") + f": {len(st.session_state.chat_history) // 2}")

        # --- 道路属性修改表格 ---
        st.write(t("edge_edit"))
        edge_list = []
        n_nodes = len(coords)
        for i in range(n_nodes):
            for j in range(n_nodes):
                if matrix[i][j]:
                    speed, lanes = matrix[i][j]
                    default_name = f"E_{i}_to_{j}"
                    current_name = st.session_state.edge_custom_names.get((i, j), default_name)
                    edge_list.append({
                        "From": i, "To": j,
                        "Name": current_name,
                        "Speed": float(speed),
                        "Lanes": int(lanes)
                    })

        if edge_list:
            edited_df = st.data_editor(
                edge_list,
                column_config={
                    "From": st.column_config.NumberColumn(disabled=True),
                    "To": st.column_config.NumberColumn(disabled=True),
                    "Name": "Edge Name",
                    "Speed": st.column_config.NumberColumn(t("col_speed"), min_value=1.0, max_value=100.0),
                    "Lanes": st.column_config.NumberColumn(t("col_lanes"), min_value=1, max_value=10)
                },
                hide_index=True,
                key="edge_editor"
            )
            # 同步回 Session State
            for index, row in pandas.DataFrame(edited_df).iterrows():
                u, v = int(row["From"]), int(row["To"])
                st.session_state.edge_custom_names[(u, v)] = row["Name"]
                st.session_state.net_data["matrix"][u][v] = [row["Speed"], row["Lanes"]]

        with c_fix:
            st.info(t("check_hint"))

            feedback = st.text_area(t("feedback_label"), height=100)

            col_btn1, col_btn2 = st.columns(2)

            # 修改按钮
            if col_btn1.button(t("fix_btn")):
                if not feedback:
                    st.warning(t("warn_input_feedback"))
                else:
                    with st.spinner(t("spinner_ai_fixing")):
                        new_res, new_hist = call_ai_to_fix(api_key, st.session_state.chat_history, feedback)
                        if new_res and new_hist:
                            new_coords, new_matrix = clean_and_parse_json(new_res)
                            if new_coords and new_matrix:
                                # 更新 Session State，刷新页面重新看图
                                st.session_state.net_data = {"coords": new_coords, "matrix": new_matrix}
                                st.session_state.chat_history = new_hist
                                st.success(t("success_net_updated"))
                                st.rerun()
                            else:
                                st.error(t("err_ai_update_fail"))
                        else:
                            st.error(t("err_ai_call_fail"))

            # 确认按钮
            if col_btn2.button(t("confirm_btn"), type="primary"):
                st.session_state.step = 3
                st.rerun()

        # 返回按钮
        if st.button(t("back_btn")):
            st.session_state.step = 1
            st.rerun()
    # --- 阶段 3: 确认路网 & 输入流量 ---
    elif st.session_state.step == 3:
        st.subheader(t("step3_title"))

        coords = st.session_state.net_data["coords"]
        matrix = st.session_state.net_data["matrix"]

        # 提取所有合法的 Edge ID 供下拉菜单使用
        valid_edges = []
        n = len(coords)
        for i in range(n):
            for j in range(n):
                if matrix[i][j]:
                    e_name = st.session_state.edge_custom_names.get((i, j), f"E_{i}_to_{j}")
                    valid_edges.append(e_name)
        valid_edges.sort()

        col_map, col_input = st.columns([1, 1])

        # 左侧：显示带标签的地图
        with col_map:
            st.write(t("net_preview_lbl"))
            fig = plot_network_with_edges(coords, matrix)
            st.pyplot(fig)

            # 后台静默生成路网文件 (为了下一步)
            # 注意：这里暂时不传 TLS 配置，等 Step 4 最终生成时再传，或者这里先传默认的
            create_sumo_network(coords, matrix, "ai_network.net.xml", edge_names=st.session_state.edge_custom_names)

        # 右侧：多流量输入
        with col_input:
            st.write(t("flow_config"))

            with st.form("flow_form"):
                c_a, c_b = st.columns(2)
                src = c_a.selectbox(t("src_edge"), valid_edges)
                dst = c_b.selectbox(t("dst_edge"), valid_edges, index=len(valid_edges) - 1)

                c_c, c_d = st.columns(2)
                cnt = c_c.number_input(t("veh_count"), 1, 10000, 200)

                # 时间设置
                c_t1, c_t2 = st.columns(2)
                t_start = c_t1.number_input(t("start_time"), 0, 3600, 0)
                t_end = c_t2.number_input(t("end_time"), 0, 7200, 3600)

                st.write(t("veh_ratio"))
                c_v1, c_v2, c_v3, c_v4 = st.columns(4)
                r_car = c_v1.number_input(t("car"), 0.0, 1.0, 0.8, step=0.1)
                r_truck = c_v2.number_input(t("truck"), 0.0, 1.0, 0.1, step=0.1)
                r_bus = c_v3.number_input(t("bus"), 0.0, 1.0, 0.1, step=0.1)
                r_moto = c_v4.number_input(t("moto"), 0.0, 1.0, 0.0, step=0.1)

                if st.form_submit_button(t("add_flow")):
                    total_ratio = r_car + r_truck + r_bus + r_moto
                    if src == dst:
                        st.error(t("err_same_edge"))
                    elif t_end <= t_start:
                        st.error(t("err_time_order"))
                    elif abs(total_ratio - 1.0) > 0.01:
                        st.error(t("err_ratio_sum", val=total_ratio))
                    else:
                        st.session_state.user_flows.append({
                            "src": src, "dst": dst, "count": cnt,
                            "start_time": t_start, "end_time": t_end,
                            "ratios": {
                                "passenger": r_car, "truck": r_truck,
                                "bus": r_bus, "motorcycle": r_moto
                            }
                        })
                        st.success(t("success_add_flow", src=src, dst=dst))

            # 显示列表 & 可编辑矩阵
            if st.session_state.user_flows:
                st.divider()
                st.write(t("flow_table_header"))
                st.caption(t("flow_table_hint"))

                # 1. 扁平化数据：把嵌套的 ratios 拆开，方便在表格里编辑
                flat_flows = []
                for f in st.session_state.user_flows:
                    # 获取 ratios，防止 key 不存在报错
                    r = f.get("ratios", {})
                    flat_flows.append({
                        "From": f["src"],
                        "To": f["dst"],
                        "Count": f["count"],
                        "Start (s)": f["start_time"],
                        "End (s)": f["end_time"],
                        "Car": r.get("passenger", 0.0),
                        "Truck": r.get("truck", 0.0),
                        "Bus": r.get("bus", 0.0),
                        "Moto": r.get("motorcycle", 0.0)
                    })

                # 转换为 Pandas DataFrame
                df_flows = pandas.DataFrame(flat_flows)

                # 2. 显示可编辑表格
                edited_df = st.data_editor(
                    df_flows,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="flow_editor",
                    column_config={
                        "From": st.column_config.SelectboxColumn(t("col_from"), options=valid_edges, required=True),
                        "To": st.column_config.SelectboxColumn(t("col_to"), options=valid_edges, required=True),
                        "Count": st.column_config.NumberColumn(t("col_count"), min_value=1, max_value=10000),
                        "Start (s)": st.column_config.NumberColumn(t("col_start"), min_value=0),
                        "End (s)": st.column_config.NumberColumn(t("col_end"), min_value=1),
                        "Car": st.column_config.NumberColumn(t("col_car"), min_value=0.0, max_value=1.0, step=0.1),
                        "Truck": st.column_config.NumberColumn(t("col_truck"), min_value=0.0, max_value=1.0, step=0.1),
                        "Bus": st.column_config.NumberColumn(t("col_bus"), min_value=0.0, max_value=1.0, step=0.1),
                        "Moto": st.column_config.NumberColumn(t("col_moto"), min_value=0.0, max_value=1.0, step=0.1),
                    }
                )
                # 3. 数据回写：将修改后的 DataFrame 重新组装回 session_state
                # 只有当数据发生变化时才执行，利用 Streamlit 的 rerun 机制自动更新
                reconstructed_flows = []
                for _, row in edited_df.iterrows():
                    # 简单的有效性检查
                    if not row["From"] or not row["To"]:
                        continue  # 跳过无效行

                    reconstructed_flows.append({
                        "src": row["From"],
                        "dst": row["To"],
                        "count": int(row["Count"]),
                        "start_time": float(row["Start (s)"]),
                        "end_time": float(row["End (s)"]),
                        "ratios": {
                            "passenger": float(row["Car"]),
                            "truck": float(row["Truck"]),
                            "bus": float(row["Bus"]),
                            "motorcycle": float(row["Moto"])
                        }
                    })

                # 更新 Session State
                st.session_state.user_flows = reconstructed_flows

                # 保留清空按钮，作为快捷方式
                if st.button(t("clear_flow"), key="btn_clear_flow"):
                    st.session_state.user_flows = []
                    st.rerun()

        st.divider()
        col_next, col_back = st.columns([3, 1])
        if col_next.button(t("next_step4"), type="primary"):
            if not st.session_state.user_flows:
                st.warning(t("warn_no_flow"))
                return
            st.session_state.step = 4
            st.rerun()
        if col_back.button(t("back_btn")):
            st.session_state.step = 2
            st.rerun()

    # --- 阶段 4: 精细化调整 ---
    elif st.session_state.step == 4:
        st.subheader(t("step4_title"))

        # 通用设置：选择要编辑的车型 (放在 Tab 外面，全局有效)
        st.write(t("veh_params"))
        v_types = ["passenger", "truck", "bus", "motorcycle"]
        selected_type = st.selectbox(t("select_type"), v_types)

        tab1, tab2, tab3, tab4 = st.tabs([t("tab_tls"), t("tab_phys"), t("tab_model"), t("tab_sim")])

        with tab4:
            st.write(t("global_sim"))
            sim_delay = st.slider(t("sim_delay"), 0, 1000, 50, help=t("help_sim_delay"))
            gen_det_logic = st.checkbox(t("gen_detectors"), value=True)

        with tab1:
            st.write(t("set_tls"))

            # 1. 加载 TLS 数据 (如果尚未加载)
            net_file = "ai_network.net.xml"
            if os.path.exists(net_file) and not st.session_state.tls_data:
                tls_data, tls_nodes = extract_tls_from_net(net_file)
                st.session_state.tls_data = tls_data
                st.session_state.tls_nodes = tls_nodes

            if not st.session_state.tls_data:
                st.info(t("no_tls_data"))
            else:
                # 2. 可视化地图
                c_map, c_edit = st.columns([1, 1])
                with c_map:
                    st.write(t("tls_map"))
                    coords = st.session_state.net_data["coords"]
                    matrix = st.session_state.net_data["matrix"]
                    fig = plot_network_with_tls(coords, matrix, st.session_state.tls_nodes)
                    st.pyplot(fig)

                # 3. 编辑器
                with c_edit:
                    tls_ids = list(st.session_state.tls_data.keys())
                    selected_tls = st.selectbox(t("select_tls"), tls_ids)

                    if selected_tls:
                        data = st.session_state.tls_data[selected_tls]
                        st.caption(f"{t('editing')} {selected_tls}")

                        # 全局属性
                        c_t1, c_t2 = st.columns(2)
                        new_type = c_t1.selectbox(t("type"), ["actuated", "static"],
                                                  index=0 if data["type"] == "actuated" else 1,
                                                  key=f"type_{selected_tls}")
                        new_offset = c_t2.number_input(t("offset"), 0.0, 300.0, float(data["offset"]),
                                                       key=f"off_{selected_tls}")

                        # 更新全局属性
                        st.session_state.tls_data[selected_tls]["type"] = new_type
                        st.session_state.tls_data[selected_tls]["offset"] = new_offset
                        if new_type == "actuated":
                            if "params" not in st.session_state.tls_data[selected_tls]:
                                st.session_state.tls_data[selected_tls]["params"] = {}

                            cur_max_gap = float(st.session_state.tls_data[selected_tls]["params"].get("max-gap", 3.0))
                            new_max_gap = st.number_input(t("max_gap"), 1.0, 10.0, cur_max_gap, help=t("help_max_gap"))
                            st.session_state.tls_data[selected_tls]["params"]["max-gap"] = new_max_gap

                        # 信号灯状态说明
                        with st.expander(t("legend")):
                            st.markdown(f"""
                            - {t("tls_state_G")}
                            - {t("tls_state_g")}
                            - {t("tls_state_y")}
                            - {t("tls_state_r")}
                            """)

                        # 相位编辑
                        st.write(t("phases"))
                        phases = data["phases"]
                        # 转换为 DataFrame 方便编辑
                        df_phases = pandas.DataFrame(phases)

                        # 确保 minDur/maxDur 列存在
                        if "minDur" not in df_phases.columns:
                            df_phases["minDur"] = df_phases["duration"]
                        if "maxDur" not in df_phases.columns:
                            df_phases["maxDur"] = df_phases["duration"]

                        column_config = {
                            "duration": st.column_config.NumberColumn("Duration (s)", min_value=1.0, max_value=300.0),
                            "state": st.column_config.TextColumn("State (G/y/r)", help=t("help_state"))
                        }

                        # Actuated 模式下显示 Min/Max Dur
                        if new_type == "actuated":
                            column_config["minDur"] = st.column_config.NumberColumn("MinDur (s)", min_value=1.0,
                                                                                    max_value=300.0)
                            column_config["maxDur"] = st.column_config.NumberColumn("MaxDur (s)", min_value=1.0,
                                                                                    max_value=300.0)

                        edited_df = st.data_editor(
                            df_phases,
                            column_config=column_config,
                            num_rows="dynamic",
                            key=f"ph_{selected_tls}"
                        )

                        # 显示连接映射
                        if "connections" in data:
                            st.write(t("connections"))
                            conns = data["connections"]
                            # Sort by index
                            sorted_indices = sorted(conns.keys())
                            conn_list = []
                            for idx in sorted_indices:
                                c = conns[idx]
                                dir_map = {
                                    "s": t("dir_s"),
                                    "l": t("dir_l"),
                                    "r": t("dir_r"),
                                    "t": t("dir_t"),
                                    "L": t("dir_L"),
                                    "R": t("dir_R")
                                }
                                conn_list.append({
                                    "Index": idx,
                                    "From": c["from"],
                                    "To": c["to"],
                                    "Dir": dir_map.get(c["dir"], c["dir"])
                                })
                            st.dataframe(conn_list, hide_index=True)
                        else:
                            st.caption(t("no_conn_info"))

                        # 保存相位回 session
                        new_phases = []
                        for idx, row in edited_df.iterrows():
                            new_phases.append({
                                "duration": float(row["duration"]),
                                "state": row["state"],
                                "minDur": float(row.get("minDur", row["duration"])),
                                "maxDur": float(row.get("maxDur", row["duration"]))
                            })

                        # 3. 只有点按钮时，才执行“存入系统”的动作
                        if st.button(t("apply_tls_changes"), key=f"save_btn_{selected_tls}"):
                            st.session_state.tls_data[selected_tls]["phases"] = new_phases
                            st.success(t("tls_saved_success"))
                            # 这里加一个特殊的强制刷新，确保数据同步
                            st.rerun()

                        total_cycle = sum(p["duration"] for p in new_phases)
                        st.caption(t("total_cycle", val=total_cycle))

                        # 计算新周期
                        total_cycle = sum(p["duration"] for p in new_phases)
                        st.caption(t("total_cycle", val=total_cycle))

                        # 4. 检查功能
                        if st.button(t("validate_btn")):
                            valid = True
                            error_msgs = []

                            # 获取预期长度
                            expected_len = 0
                            if "connections" in data and data["connections"]:
                                expected_len = len(data["connections"])
                            elif phases:
                                expected_len = len(phases[0]["state"])

                            for i, p in enumerate(new_phases):
                                s = p["state"]
                                d = p["duration"]

                                # 检查时长
                                if d <= 0:
                                    valid = False
                                    error_msgs.append(t("err_duration", i=i + 1))

                                # 检查长度
                                if len(s) != expected_len:
                                    valid = False
                                    error_msgs.append(t("err_len", i=i + 1, len=len(s), exp=expected_len))

                                # 检查字符
                                if not all(c in "Ggyr" for c in s):
                                    valid = False
                                    error_msgs.append(t("err_char", i=i + 1))

                            if valid:
                                st.success(t("valid_phases"))
                            else:
                                st.error(t("invalid_phases"))
                                for msg in error_msgs:
                                    st.write(f"- {msg}")

        with tab2:
            st.caption(f"{t('editing')} {selected_type}")

            # 初始化该车型的参数
            defaults = {
                "passenger": {"length": 5.0, "maxSpeed": 50.0, "accel": 2.6, "decel": 4.5},
                "truck": {"length": 7.0, "maxSpeed": 30.0, "accel": 1.5, "decel": 3.0},
                "bus": {"length": 12.0, "maxSpeed": 25.0, "accel": 1.2, "decel": 2.5},
                "motorcycle": {"length": 2.5, "maxSpeed": 55.0, "accel": 5.0, "decel": 6.0}
            }

            current_params = st.session_state.vtype_params.get(selected_type, defaults[selected_type])

            c1, c2 = st.columns(2)
            new_len = c1.number_input(t("lbl_veh_len"), 1.0, 30.0, float(current_params["length"]),
                                      key=f"len_{selected_type}")
            new_speed = c2.number_input(t("lbl_max_speed"), 1.0, 100.0, float(current_params["maxSpeed"]),
                                        key=f"spd_{selected_type}")
            new_accel = c1.number_input(t("lbl_max_accel"), 0.1, 10.0, float(current_params["accel"]),
                                        key=f"acc_{selected_type}")
            new_decel = c2.number_input(t("lbl_max_decel"), 0.1, 10.0, float(current_params["decel"]),
                                        key=f"dec_{selected_type}")

            # 保存回 session
            if selected_type not in st.session_state.vtype_params:
                st.session_state.vtype_params[selected_type] = {}
            st.session_state.vtype_params[selected_type].update({
                "length": new_len, "maxSpeed": new_speed, "accel": new_accel, "decel": new_decel
            })

        with tab3:
            st.caption(f"{t('editing')} {selected_type}")

            # 默认值
            cur_cf = st.session_state.vtype_params.get(selected_type, {}).get("carFollowModel", "Krauss")
            cur_gap = st.session_state.vtype_params.get(selected_type, {}).get("minGap", 2.5)
            cur_tau = st.session_state.vtype_params.get(selected_type, {}).get("tau", 1.0)
            cur_lc = st.session_state.vtype_params.get(selected_type, {}).get("lcStrategic", 1.0)

            # 跟驰模型
            cf_model = st.selectbox(t("lbl_cf_model"), ["Krauss", "IDM", "Wiedemann"],
                                    index=["Krauss", "IDM", "Wiedemann"].index(cur_cf) if cur_cf in ["Krauss", "IDM",
                                                                                                     "Wiedemann"] else 0,
                                    key=f"cf_{selected_type}")

            # 通用跟驰参数
            c_cf1, c_cf2 = st.columns(2)
            min_gap = c_cf1.number_input(t("lbl_min_gap"), 0.0, 10.0, float(cur_gap), key=f"gap_{selected_type}")
            tau = c_cf2.number_input(t("lbl_tau"), 0.1, 3.0, float(cur_tau), key=f"tau_{selected_type}")

            # 模型特定参数
            cf_params = {}
            if cf_model == "Krauss":
                cur_sigma = st.session_state.vtype_params.get(selected_type, {}).get("sigma", 0.5)
                sigma = st.slider(t("lbl_sigma"), 0.0, 1.0, float(cur_sigma), help=t("help_sigma"),
                                  key=f"sigma_{selected_type}")
                cf_params["sigma"] = sigma

            elif cf_model == "IDM":
                cur_delta = st.session_state.vtype_params.get(selected_type, {}).get("delta", 4.0)
                cur_step = st.session_state.vtype_params.get(selected_type, {}).get("stepping", 0.25)

                c_idm1, c_idm2 = st.columns(2)
                delta = c_idm1.number_input(t("lbl_delta"), 1.0, 10.0, float(cur_delta), help=t("help_delta"),
                                            key=f"delta_{selected_type}")
                stepping = c_idm2.number_input(t("lbl_stepping"), 0.01, 1.0, float(cur_step), help=t("help_stepping"),
                                               key=f"step_{selected_type}")

                cf_params["delta"] = delta
                cf_params["stepping"] = stepping

            elif cf_model == "Wiedemann":
                cur_sec = st.session_state.vtype_params.get(selected_type, {}).get("security", 0.5)
                cur_est = st.session_state.vtype_params.get(selected_type, {}).get("estimation", 0.5)

                c_w1, c_w2 = st.columns(2)
                security = c_w1.number_input(t("lbl_security"), 0.1, 10.0, float(cur_sec), key=f"sec_{selected_type}")
                estimation = c_w2.number_input(t("lbl_estimation"), 0.1, 10.0, float(cur_est),
                                               key=f"est_{selected_type}")

                cf_params["security"] = security
                cf_params["estimation"] = estimation

            st.divider()
            st.write(t("header_lc_params"))

            # 换道模型参数
            cur_lc_coop = st.session_state.vtype_params.get(selected_type, {}).get("lcCooperative", 1.0)
            cur_lc_gain = st.session_state.vtype_params.get(selected_type, {}).get("lcSpeedGain", 1.0)
            cur_lc_right = st.session_state.vtype_params.get(selected_type, {}).get("lcKeepRight", 1.0)
            cur_lc_assert = st.session_state.vtype_params.get(selected_type, {}).get("lcAssertive", 1.0)

            c_lc1, c_lc2 = st.columns(2)
            lc_strat = c_lc1.slider(t("lbl_lc_strat"), 0.0, 10.0, float(cur_lc), help=t("help_lc_strat"),
                                    key=f"lc_{selected_type}")
            lc_coop = c_lc2.slider(t("lbl_lc_coop"), 0.0, 1.0, float(cur_lc_coop), help=t("help_lc_coop"),
                                   key=f"lccoop_{selected_type}")

            c_lc3, c_lc4 = st.columns(2)
            lc_gain = c_lc3.number_input(t("lbl_lc_gain"), 0.0, 10.0, float(cur_lc_gain), help=t("help_lc_gain"),
                                         key=f"lcgain_{selected_type}")
            lc_right = c_lc4.number_input(t("lbl_lc_right"), 0.0, 10.0, float(cur_lc_right), help=t("help_lc_right"),
                                          key=f"lcright_{selected_type}")

            lc_assert = st.slider(t("lbl_lc_assert"), 1.0, 10.0, float(cur_lc_assert), help=t("help_lc_assert"),
                                  key=f"lcassert_{selected_type}")

            # 保存所有参数
            update_dict = {
                "carFollowModel": cf_model,
                "minGap": min_gap,
                "tau": tau,
                "lcStrategic": lc_strat,
                "lcCooperative": lc_coop,
                "lcSpeedGain": lc_gain,
                "lcKeepRight": lc_right,
                "lcAssertive": lc_assert
            }
            update_dict.update(cf_params)  # 合并特定模型的参数

            st.session_state.vtype_params[selected_type].update(update_dict)

        st.divider()
        col_start, col_back = st.columns([3, 1])
        if col_start.button(t("start_sim"), type="primary"):
            # 1. 重新生成路网 (带 TLS 配置)
            coords = st.session_state.net_data["coords"]
            matrix = st.session_state.net_data["matrix"]
            create_sumo_network(coords, matrix, "ai_network.net.xml",
                                edge_names=st.session_state.edge_custom_names,
                                tls_config=st.session_state.tls_config)

            # 2. 生成流量 (带车型参数)
            rou, add_det = generate_traffic_by_edges("ai_network.net.xml",
                                                     st.session_state.user_flows,
                                                     vtype_params=st.session_state.vtype_params,generate_detectors=gen_det_logic )

            # 3. 生成 TLS 配置文件
            add_tls = None
            final_net_file = "ai_network.net.xml"

            if st.session_state.tls_data:
                add_tls = generate_tls_add_file(st.session_state.tls_data, "tls.add.xml")

                # 关键修复: 使用 netconvert 将 TLS 配置合并到路网文件中
                # 避免 "Another logic with id ... exists" 错误
                if add_tls and sumo_bin:
                    merged_net_file = "ai_network_merged.net.xml"
                    st.caption(t("caption_merging_tls"))
                    netconvert_cmd = [
                        os.path.join(sumo_bin, "netconvert"),
                        "-s", "ai_network.net.xml",
                        "-i", add_tls,
                        "-o", merged_net_file
                    ]
                    try:
                        subprocess.run(netconvert_cmd, check=True, capture_output=True)
                        final_net_file = merged_net_file
                        # 合并成功后，不需要再作为 additional file 加载，否则会冲突
                        add_tls = None
                    except subprocess.CalledProcessError as e:
                        st.error(t("err_merge_tls", e=e))
                        # 如果合并失败，尝试继续运行（可能会报错，但至少给用户反馈）

            # 合并 additional 文件
            add_files = []
            if add_det: add_files.append(add_det)
            if add_tls: add_files.append(add_tls)  # 只有在合并失败或未合并时才添加
            final_add_file = ",".join(add_files) if add_files else None

            if rou:
                open_in_sumo_gui(final_net_file, rou, final_add_file, delay=sim_delay)

        # 返回按钮
        if col_back.button(t("back_btn")):
            st.session_state.step = 3
            st.rerun()

    st.divider()
    st.subheader(t("results_title"))

    # 添加一个刷新按钮，因为仿真运行时文件会动态更新
    if st.button(t("refresh_det")):
        det_file = "det_out.xml"

        if os.path.exists(det_file):
            try:
                # 1. 读取 XML 文件
                tree = ET.parse(det_file)
                root = tree.getroot()

                # 2. 解析为列表
                data = []
                for interval in root.findall('interval'):
                    data.append({
                        "Edge/Lane ID": interval.get('id'),
                        "Time Start": float(interval.get('begin')),
                        "Time End": float(interval.get('end')),
                        "Vehicle Count": int(interval.get('nVehContrib')),
                        "Avg Speed (m/s)": float(interval.get('speed')),
                        "Occupancy (%)": float(interval.get('occupancy'))
                    })

                # 3. 如果有数据，显示为表格
                if data:
                    st.success(t("success_read", count=len(data)))
                    st.dataframe(data)

                    # 简单可视化：展示最拥堵的路段 (Occupancy 最高的)
                    import pandas as pd
                    df = pd.DataFrame(data)
                    # 过滤掉没有车的记录，避免图表太乱
                    active_df = df[df["Vehicle Count"] > 0]

                    if not active_df.empty:
                        st.write(t("chart_title"))
                        st.bar_chart(active_df.set_index("Edge/Lane ID")["Avg Speed (m/s)"])
                    else:
                        st.info(t("no_veh"))

                else:
                    st.warning(t("wait_data"))

            except Exception as e:
                st.error(t("err_read_file", e=e))
        else:
            st.warning(t("no_det_file"))


if __name__ == "__main__":
    main()