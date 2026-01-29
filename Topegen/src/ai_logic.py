import re
import json
import datetime
import os
from PIL import Image
import google.generativeai as genai
import streamlit as st
def build_multimodal_prompt(user_text=None, has_image=False):
    """构建适用于图像+文本理解的 Prompt"""
    prompt_parts = []

    if has_image:
        prompt_parts.append(
            "你是一个交通工程专家，擅长从草图或地图中提取道路网络结构。"
            "请分析用户提供的图像和/或文字描述，识别出所有道路和交叉口（节点）和道路连接（边）。"
        )
    else:
        prompt_parts.append(
            "你是一个交通仿真助手，请将用户的自然语言描述转化为结构化路网数据。"
        )

    prompt_parts.append(
        "请返回一个严格 JSON 对象，包含两个字段：\n"
        "1. \"node_coordinates\": [[x1,y1], [x2,y2], ...] —— 节点地理坐标（单位：米）\n"
        "2. \"adjacency_matrix\": N×N 数组 —— 有向连接矩阵\n\n"

        "【图像分析关键约束】(针对图像输入必须严格遵守)\n"
        "1. **编号一致性**：如果图像中明确标注了节点编号（如 0, 1, 2...）(所有编号都是节点编号，没有边编号)，请务必让 `node_coordinates` 列表中的索引与图像上的编号一一对应。例如：图像上的\"节点0\"必须是列表的第1个元素。\n"
        "2. **几何比例保持**：请严格保持图像中的相对几何比例。长路段与短路段的长度比值应与视觉呈现一致。\n"
        "3. **不存在孤立节点**：所有节点都至少与一个节点相连"

        "【节点坐标规则】⚠️ 重要\n"
        "- **禁止使用 null**：node_coordinates 数组中的每个元素都必须是有效的 [x, y] 坐标对\n"
        "- **所有节点必须有坐标**：不能跳过节点或使用 null 占位\n"
        "- **坐标必须是数字**：x 和 y 都必须是数值类型，不能是 null、字符串或其他类型\n"
        "- **正确示例**: [[0,0], [100,0], [50,87]] ✓\n"
        "- **错误示例**: [[0,0], null, [50,87]] ✗\n\n"

        "【邻接矩阵规则】\n"
        "- matrix[i][j] 表示从节点 i 到 j 的单向道路\n"
        "- 若双向通行，请同时设置 matrix[i][j] 和 matrix[j][i]\n"
        "- 元素格式: [speed_mps (float), num_lanes (int)]，例如 [13.9, 2]\n"
        "- 无连接写 null（仅在邻接矩阵中允许使用null）\n\n"

        "【默认值】\n"
        "- 若未明确说明，车道数=1，速度=13.9 m/s (~50 km/h)\n"
        "- 弯道可用多个节点拟合\n"
        "- 节点应位于交叉口或道路端点\n\n"
        "- 所有节点都应至少与其他某一节点连接，不存在孤立节点\n\n"

        "【示例输出】\n"
        "{\n"
        "  \"node_coordinates\": [[0,0], [100,0], [50,87]],\n"
        "  \"adjacency_matrix\": [\n"
        "    [null, [13.9, 2], [13.9, 1]],\n"
        "    [[13.9, 2], null, [13.9, 1]],\n"
        "    [[13.9, 1], [13.9, 1], null]\n"
        "  ]\n"
        "}\n\n"

        "⚠️ 注意：只返回纯 JSON，不要包含任何解释、Markdown 代码块标记或其他文字！\n"
        "⚠️ 特别注意：node_coordinates 中绝对不能有 null 值！"
    )

    if user_text:
        prompt_parts.append(f"📌 用户补充说明: \"{user_text}\"")
    return "\n".join(prompt_parts)


def call_google_ai_vision(api_key, text_prompt=None, image_file=None):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    inputs = []
    if image_file:
        inputs.append(Image.open(image_file))
    if text_prompt: inputs.append(text_prompt)
    try:
        # 开启聊天模式 (history=[])
        chat = model.start_chat(history=[])
        response = chat.send_message(inputs)
        return response.text.strip(), chat.history  # 返回内容和历史
    except Exception as e:
        st.error(t("err_ai", e=e))
        return None, None


def call_ai_to_fix(api_key, history, user_feedback):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    try:
        # 加载之前的历史 (实现记忆功能)
        chat = model.start_chat(history=history)

        # 发送修改指令，并强制要求返回完整 JSON
        prompt = f"""
        用户修改意见: "{user_feedback}"
        请根据上下文修改之前的路网数据。
        必须返回修改后完整的纯 JSON 对象 (包含 node_coordinates 和 adjacency_matrix)。
        """
        response = chat.send_message(prompt)
        return response.text.strip(), chat.history  # 返回新内容和更新后的历史
    except Exception as e:
        st.error(t("err_ai_fix", e=e))
        return None, None


def clean_and_parse_json(raw_text):
    try:
        cleaned = re.sub(r'^```(?:json)?\s*|```$', '', raw_text.strip())
        data = json.loads(cleaned)
        return data.get("node_coordinates"), data.get("adjacency_matrix")
    except:
        return None, None

def save_ai_conversation_to_txt(ai_name, round_num, prompt, response, image_desc=None):
    """
    保存单次AI对话到TXT文件

    Args:
        ai_name: AI名称 (如 "AI1", "AI2")
        round_num: 对话轮次
        prompt: 发送给AI的提示词
        response: AI的响应
        image_desc: 图像描述(如果有)

    Returns:
        保存的文件路径
    """
    log_dir = "ai_chat_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = os.path.join(log_dir, f"{ai_name}_Round{round_num}_{timestamp}.txt")

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\\n")
            f.write(f"  {ai_name} 对话记录 - 第 {round_num} 轮\\n")
            f.write(f"  时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
            f.write("=" * 80 + "\\n\\n")

            if image_desc:
                f.write("━━━ 图像信息 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n")
                f.write(f"{image_desc}\\n\\n")

            f.write("━━━ 提示词 (Prompt) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n")
            f.write(prompt + "\\n\\n")

            f.write("━━━ AI响应 (Response) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n")
            f.write(response + "\\n\\n")

            f.write("=" * 80 + "\\n")

        return filename
    except Exception as e:
        print(f"保存对话记录失败: {e}")
        return None


def ai_cross_verification(api_key, api_key_ai2, original_prompt, ai1_response, image_file=None):
    """
    双AI交叉验证核心函数 (修复版: 支持图像传输与记忆保持)
    """
    # 验证过程消息列表
    verification_msgs = []

    def add_msg(msg_type, msg):
        """添加消息到列表"""
        verification_msgs.append({"type": msg_type, "msg": msg})
        # 同时在界面显示
        if msg_type == "success":
            st.success(msg)
        elif msg_type == "warning":
            st.warning(msg)
        elif msg_type == "info":
            st.info(msg)
        elif msg_type == "write":
            st.write(msg)

    # 准备图像对象 (如果存在)
    img_obj = None
    if image_file:
        try:
            # 重新打开图像，确保指针在开始位置
            image_file.seek(0)
            img_obj = Image.open(image_file)
        except Exception as e:
            add_msg("warning", f"⚠️ 图像加载失败: {e}")

    # ==========================================
    # 1. 初始化 AI1 (带记忆)
    # ==========================================
    genai.configure(api_key=api_key)
    model_ai1 = genai.GenerativeModel('gemini-2.5-flash')

    # 构建 AI1 的初始历史，让它“记得”自己刚刚生成了什么
    # 这里模拟了上一轮的对话
    ai1_history = [
        {"role": "user", "parts": [original_prompt]},
        {"role": "model", "parts": [ai1_response]}
    ]
    if img_obj:
        # 如果有图，历史记录里的第一条用户消息也要加上图
        ai1_history[0]["parts"].insert(0, img_obj)

    # 启动 AI1 会话 (在循环外)
    chat_ai1 = model_ai1.start_chat(history=ai1_history)

    # ==========================================
    # 2. 初始化 AI2 (在循环外，保持验证过程中的记忆)
    # ==========================================
    # 注意：配置 AI2 需要切换 Key，但在创建对象时先暂存 Model
    # 实际调用前我们会再次 configure 确保 Key 正确
    model_ai2 = genai.GenerativeModel('gemini-2.5-flash')
    chat_ai2 = None  # 稍后初始化

    log_files = []
    max_rounds = 3

    # 保存AI1初始方案
    log_file = save_ai_conversation_to_txt(
        "AI1", 0, original_prompt, ai1_response,
        "用户提供了草图图像" if image_file else None
    )
    if log_file:
        log_files.append(log_file)

    current_ai1_solution = ai1_response
    last_ai1_reason = "初始方案生成" # 新增：记录AI1的理由
    ai1_coords, ai1_matrix = clean_and_parse_json(current_ai1_solution)

    ai2_corrected = None
    ai2_coords = None
    ai2_matrix = None

    for round_num in range(1, max_rounds + 1):
        add_msg("write", f"🔄 验证轮次: {round_num}/{max_rounds}")

        # ===== Step 1: AI2验证AI1的方案 =====
        ai1_context = f"【AI1的方案理由】: {last_ai1_reason}" if round_num > 1 else ""
        verification_prompt = f"""你是一个交通工程审核专家,请验证另一个AI生成的路网方案是否正确。

【原始用户需求】
{original_prompt}

{"注意:用户还提供了草图图像作为参考，请务必比对图像中的节点编号和连接关系！" if image_file else ""}

【AI1生成的方案】
{current_ai1_solution}
{ai1_context}

【验证任务】
请仔细检查AI1的方案是否满足以下要求:
1. 节点坐标是否与需求描述一致 ，节点数量是否正确(如果有图，请严格比对图片)
2. 邻接矩阵的连接关系是否正确，边的条数是否正确(单向/双向)
3. 车道数和速度设置是否合理
4. 是否存在逻辑错误或遗漏

【返回格式】
请返回一个JSON对象,包含以下字段:
{{
  "is_correct": true/false,
  "evaluation": "详细的评价说明，并在此处告诉我你有没有收到图片",
  "issues": ["问题1", "问题2", ...],
  "corrected_solution": {{
    "node_coordinates": [...],
    "adjacency_matrix": [...]
  }}
}}

注意:
- 如果is_correct=true,则corrected_solution可以省略
- 如果is_correct=false,必须在corrected_solution中提供修正方案
- 只返回纯JSON,不要包含任何解释或Markdown标记!
- 如果错误过多,issues无需每条列出,直接给出告知错误过多,给出最终方案
"""

        try:
            # 切换到 AI2 的 Key
            genai.configure(api_key=api_key_ai2)

            # 如果是第一轮，初始化 chat_ai2
            if chat_ai2 is None:
                chat_ai2 = model_ai2.start_chat(history=[])

            # 构建发送给 AI2 的内容列表 (混合文本和图片)
            ai2_inputs = [verification_prompt]
            if img_obj:
                ai2_inputs.insert(0, img_obj)  # 把图片放在最前面

            # 发送消息
            ai2_response = chat_ai2.send_message(ai2_inputs)
            ai2_text = ai2_response.text.strip()

            # 保存AI2对话
            log_file = save_ai_conversation_to_txt("AI2", round_num, verification_prompt, ai2_text)
            if log_file:
                log_files.append(log_file)

            # 记录AI2原始返回内容
            add_msg("info", f"📝 AI2原始返回 (前200字符): {ai2_text[:200]}...")

            # 解析AI2的验证结果 - 改进的JSON提取逻辑
            def extract_json_from_text(text):
                # ... (保持原本的 JSON 提取逻辑不变) ...
                try:
                    return json.loads(text)
                except:
                    pass
                cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
                cleaned = re.sub(r'```$', '', cleaned.strip())
                try:
                    return json.loads(cleaned)
                except:
                    pass
                json_match = re.search(r'\{[\s\S]*\}', text)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except:
                        pass
                if "正确" in text or "correct" in text.lower() or "is_correct" in text:
                    return {"is_correct": True, "evaluation": text}
                return None

            ai2_result = extract_json_from_text(ai2_text)
            if ai2_result is None:
                add_msg("warning", f"⚠️ AI2返回内容无法解析为JSON，原始内容已记录在日志中")
                break

            # 如果AI2认为正确,验证通过
            if ai2_result.get("is_correct", False):
                add_msg("success", "✅ AI2验证通过:方案正确!")
                st.session_state.verification_messages = verification_msgs
                return ai1_coords, ai1_matrix, True, None, None, log_files

            # AI2认为有问题,提取修正方案
            ai2_corrected = ai2_result.get("corrected_solution")
            if not ai2_corrected:
                add_msg("warning", f"⚠️ AI2认为方案有误但未提供修正方案,使用AI1方案")
                break

            ai2_coords = ai2_corrected.get("node_coordinates")
            ai2_matrix = ai2_corrected.get("adjacency_matrix")

            add_msg("info", f"ℹ️ AI2发现问题: {ai2_result.get('evaluation', '未说明')}")

        except Exception as e:
            add_msg("warning", f"⚠️ AI2验证出错(第{round_num}轮): {e}")
            break

        # ===== Step 2: AI1评估AI2的修正方案 =====
        review_prompt = f"""另一个审核专家(AI2)认为你之前的方案存在问题,并提出了修正方案。

【AI2的评价】
{ai2_result.get('evaluation', '')}

【AI2指出的问题】
{json.dumps(ai2_result.get('issues', []), ensure_ascii=False, indent=2)}

【AI2的修正方案】
{json.dumps(ai2_corrected, ensure_ascii=False, indent=2)}

【请你判断】
请评估AI2的修正方案是否合理。返回JSON格式:
{{
  "agree": true/false,
  "reason": "你的理由说明，并在此处告诉我你是否记得原始要求以及之前的讨论内容",
  "final_solution": {{
    "node_coordinates": [...],
    "adjacency_matrix": [...]
  }}
}}

注意:
- 如果agree=true,在final_solution中返回AI2的方案
- 如果agree=false,在final_solution中返回你坚持的方案(可以是原方案或改进版)
- 只返回纯JSON,不要任何解释!
"""

        try:
            # 切换回 AI1 的 Key
            genai.configure(api_key=api_key)

            # 直接使用之前创建的 chat_ai1，保持记忆
            ai1_review_response = chat_ai1.send_message(review_prompt)
            ai1_review_text = ai1_review_response.text.strip()

            # 保存AI1的评估对话
            log_file = save_ai_conversation_to_txt("AI1", round_num, review_prompt, ai1_review_text)
            if log_files:
                log_files.append(log_file)

            add_msg("info", f"📝 AI1评估返回 (前200字符): {ai1_review_text[:200]}...")

            ai1_review = extract_json_from_text(ai1_review_text)
            last_ai1_reason = ai1_review.get("reason", "坚持原方案")
            if ai1_review is None:
                add_msg("warning", f"⚠️ AI1返回内容无法解析为JSON")
                raise Exception("AI1返回格式错误")

            # 如果AI1同意AI2的方案
            if ai1_review.get("agree", False):
                add_msg("success", f"✅ AI1同意AI2的方案! 原因: {ai1_review.get('reason', '')}")
                final_solution = ai1_review.get("final_solution", ai2_corrected)
                final_coords = final_solution.get("node_coordinates")
                final_matrix = final_solution.get("adjacency_matrix")
                return final_coords, final_matrix, True, None, None, log_files

            # AI1不同意,更新当前AI1方案
            add_msg("warning", f"⚠️ AI1不同意AI2方案: {ai1_review.get('reason', '')}")
            current_ai1_solution = json.dumps(ai1_review.get("final_solution"), ensure_ascii=False)
            ai1_coords, ai1_matrix = clean_and_parse_json(current_ai1_solution)

        except Exception as e:
            add_msg("warning", f"⚠️ AI1评估出错(第{round_num}轮): {e}")
            # 使用AI2的方案
            st.session_state.verification_messages = verification_msgs
            return ai2_coords, ai2_matrix, False, current_ai1_solution, json.dumps(ai2_corrected,
                                                                                   ensure_ascii=False), log_files

    # 3轮后仍未达成一致
    add_msg("warning", "⚠️ 3轮验证后,两个AI未能达成一致")
    ai2_final_str = json.dumps(ai2_corrected, ensure_ascii=False) if ai2_corrected else None
    st.session_state.verification_messages = verification_msgs
    return None, None, False, current_ai1_solution, ai2_final_str, log_files