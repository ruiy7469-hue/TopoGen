import re
import json
import datetime
import os
from PIL import Image
import google.generativeai as genai
import streamlit as st
from language import t
from openai import OpenAI
import base64  # 新增：用于将图片转码
import io      # 新增：用于处理图片流

def encode_image_to_base64(image_file):
    """将 Streamlit 上传的图片对象转换为 Base64 编码"""
    try:
        if image_file is None:
            return None
        # 使用 getvalue 直接获取二进制数据，不需要 seek(0)
        import base64
        return base64.b64encode(image_file.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"图片转码失败: {e}")
        return None

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
        "- 若未明确说明，车道数=1，速度=13.9 m/s (~50 km/h),所有道路默认双向连接\n"
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


def call_llm_engine(model_brand, api_key, prompt, history=None, image_file=None):
    """通用多模态引擎：支持 Gemini 和 OpenAI 格式的图文输入"""
    if history is None: history = []
    temp = st.session_state.get("temp")

    # --- 情况 A: 如果是 Gemini (Google) ---
    if model_brand == "Gemini":
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # 1. 准备好要发送的内容
        if image_file:
            inputs = [Image.open(image_file), prompt]
        else:
            inputs = prompt

        # 2. 开启对话
        chat = model.start_chat(history=history)

        # 3. 发送我们刚才准备好的 inputs，并带上温度参数
        response = chat.send_message(
            inputs,
            generation_config=genai.types.GenerationConfig(temperature=temp)
        )
        return response.text.strip(), chat.history

    # --- 情况 B: 如果是 OpenAI 格式 (DeepSeek, 千问等) ---
    else:
        b_url, m_name = "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3-vl-flash"  # 注意：千问看图需用 qwen-vl 系列

        client = OpenAI(api_key=api_key, base_url=b_url)

        # 1. 处理历史记录转换
        messages = []
        for h in history:
            role = "user" if h["role"] == "user" else "assistant"
            messages.append({"role": role, "content": h["parts"][0]})

        # 2. 【关键】组装当前的消息内容
        current_content = []

        # 如果有图片，按照多模态格式添加图片信息
        if image_file:
            base64_str = encode_image_to_base64(image_file)
            current_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_str}"}
            })

        # 添加文字 Prompt
        current_content.append({"type": "text", "text": prompt})

        # 3. 合并到消息列表
        messages.append({"role": "user", "content": current_content})

        # 4. 发送请求


        response = client.chat.completions.create(
            model=m_name,
            messages=messages,
            temperature=temp,  # <--- 【关键修改】：在此处应用温度参数
            stream=False
            )
        ans_text = response.choices[0].message.content

        # 模拟 Gemini 格式返回记忆
        new_history = history + [
            {"role": "user", "parts": [prompt]},
            {"role": "model", "parts": [ans_text]}
        ]
        return ans_text.strip(), new_history

def call_google_ai_vision(api_key, text_prompt=None, image_file=None):
    # 自动从网页侧边栏获取你选的是哪个模型
    brand = st.session_state.get("selected_model")
    return call_llm_engine(brand, api_key, text_prompt, image_file=image_file)


def call_ai_to_fix(api_key, history, user_feedback):
    brand = st.session_state.get("selected_model")
    prompt = f"用户修改意见: {user_feedback}\n请修改路网数据并返回完整JSON。"
    return call_llm_engine(brand, api_key, prompt, history=history)


def clean_and_parse_json(raw_text):
    """
    暴力级解析器：支持 strict=False 容错模式，处理嵌套结构，防止 NoneType 报错
    """
    if not raw_text or str(raw_text).lower() == "null":
        return None, None

    try:
        # 1. 预处理：去掉 Markdown 标签
        text = re.sub(r'```(?:json)?', '', raw_text, flags=re.IGNORECASE)
        text = text.replace('```', '').strip()

        # 2. 定位大括号：抓取第一个 { 到最后一个 } 之间的所有内容
        match = re.search(r'(\{[\s\S]*\})', text)
        if not match:
            return None, None

        json_str = match.group(1)

        # 3. 【核心修正】使用 strict=False 允许 AI 在 JSON 字符串中直接换行
        # 同时处理一下可能的控制字符
        data = json.loads(json_str, strict=False)

        if not data or not isinstance(data, dict):
            return None, None

        # 4. 【重要】处理嵌套逻辑
        # 你的 AI 往往会返回 {"agree": false, "final_solution": {...}}
        # 我们需要判断数据是在顶层，还是在 final_solution 里面
        coords = data.get("node_coordinates")
        matrix = data.get("adjacency_matrix")

        if coords is None and "final_solution" in data:
            inner = data.get("final_solution")
            if isinstance(inner, dict):
                coords = inner.get("node_coordinates")
                matrix = inner.get("adjacency_matrix")

        return coords, matrix

    except Exception as e:
        print(f"DEBUG: JSON 解析最终失败。原因: {e}")
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
    双AI交叉验证核心函数 (通用适配版)
    """
    verification_msgs = []

    def add_msg(msg_type, msg):
        if msg_type == "success":
            st.success(msg)
        elif msg_type == "warning":
            st.warning(msg)
        elif msg_type == "info":
            st.info(msg)
        else:
            st.write(msg)
        verification_msgs.append({"type": msg_type, "msg": msg})

    # --- 改进的JSON提取逻辑 (移到循环外) ---
    def extract_json_from_text(text):
        if not text: return None

        # 统一调用刚才写好的逻辑
        # 我们稍微变通一下，因为这里需要返回整个字典，而不仅仅是坐标
        try:
            # 同样：清理反引号 -> 定位 {}
            t = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.IGNORECASE)
            t = re.sub(r'\s*```$', '', t.strip())
            match = re.search(r'(\{[\s\S]*\})', t)
            json_str = match.group(1) if match else t

            return json.loads(json_str)
        except:
            # 最后的保底逻辑：如果 AI 在文字里提到了“正确”，则认为是 true
            if "正确" in text or "correct" in text.lower():
                return {"is_correct": True, "evaluation": "AI判断方案正确"}
            return None

    # ==========================================
    # 1. 准备环境 (移出缩进，确保文字模式可用)
    # ==========================================
    brand = st.session_state.get("selected_model", "Gemini")

    # 初始化 AI1 的记忆（通用列表格式）
    ai1_history = [
        {"role": "user", "parts": [original_prompt]},
        {"role": "model", "parts": [ai1_response]}
    ]

    current_ai1_solution = ai1_response
    last_ai1_reason = "初始方案生成"
    log_files = []
    max_rounds = 3

    # 提前解析 AI1 的初始结果
    ai1_coords, ai1_matrix = clean_and_parse_json(current_ai1_solution)

    # ==========================================
    # 2. 验证循环
    # ==========================================
    for round_num in range(1, max_rounds + 1):
        add_msg("write", f"🔄 验证轮次: {round_num}/{max_rounds}")

        # ----- Step 1: AI2 (审核员) 验证 AI1 -----
        ai1_context = f"【AI1的方案理由】: {last_ai1_reason}" if round_num > 1 else ""
        verification_prompt = f"""你是一个交通工程审核专家,请验证另一个AI生成的路网方案是否正确。
【原始用户需求】: {original_prompt}
【AI1生成的方案】: {current_ai1_solution}
{ai1_context}
请检查坐标、邻接矩阵逻辑、车道数是否合理，理由里先告诉我你是什么模型，再描述一下路网画面，并且告诉我你能否看到图片。
返回JSON格式: {{"is_correct": true/false, "evaluation": "...", "corrected_solution": {{...}}}}
"""
        try:
            # 调用通用引擎，如果有图会自动处理
            ai2_text, _ = call_llm_engine(
                brand, api_key_ai2, verification_prompt, image_file=image_file
            )

            log_file = save_ai_conversation_to_txt("AI2", round_num, verification_prompt, ai2_text)
            if log_file: log_files.append(log_file)

            ai2_result = extract_json_from_text(ai2_text)
            if ai2_result is None:
                add_msg("warning", "⚠️ AI2返回无法解析，尝试信任AI1方案。")
                break

            if ai2_result.get("is_correct", False):
                add_msg("success", "✅ AI2验证通过！")
                st.session_state.verification_messages = verification_msgs
                return ai1_coords, ai1_matrix, True, None, None, log_files

            ai2_corrected = ai2_result.get("corrected_solution")
            add_msg("info", f"ℹ️ AI2发现问题: {ai2_result.get('evaluation', '未说明')}")

        except Exception as e:
            add_msg("warning", f"⚠️ AI2故障: {e}")
            break

        # ----- Step 2: AI1 (设计者) 评估 AI2 的修正 -----
        review_prompt = f"""审核专家(AI2)认为你的方案有误。
【AI2评价】: {ai2_result.get('evaluation')}
【AI2修正方案】: {json.dumps(ai2_corrected)}
请评估是否合理，若同意请在final_solution返回AI2的方案，若坚持自己请返回你的理由和方案,理由里先告诉我你是什么模型，再描述一下路网画面，并且告诉我你能否看到图片。
返回JSON: {{"agree": true/false, "reason": "...", "final_solution": {{...}}}}
"""
        try:
            # 调用通用引擎，带上历史记录实现记忆
            ai1_review_text, ai1_history = call_llm_engine(
                brand, api_key, review_prompt, history=ai1_history
            )

            log_file = save_ai_conversation_to_txt("AI1", round_num, review_prompt, ai1_review_text)
            if log_file: log_files.append(log_file)

            ai1_review = extract_json_from_text(ai1_review_text)
            if ai1_review is None: raise Exception("AI1返回格式错误")

            last_ai1_reason = ai1_review.get("reason", "坚持原方案")

            if ai1_review.get("agree", False):
                add_msg("success", f"✅ AI1同意了AI2的修正方案。")
                final = ai1_review.get("final_solution", ai2_corrected)
                return final.get("node_coordinates"), final.get("adjacency_matrix"), True, None, None, log_files

            # 不同意则继续循环
            add_msg("warning", f"⚠️ AI1不同意修正: {last_ai1_reason}")
            new_sol_from_ai = ai1_review.get("final_solution")
            if new_sol_from_ai and isinstance(new_sol_from_ai, dict):
                # 只有当 AI 确实吐出了有效的 JSON 字典时才更新
                current_ai1_solution = json.dumps(new_sol_from_ai, ensure_ascii=False)
                # 更新坐标，供下一轮可视化/验证使用
                temp_coords, temp_matrix = clean_and_parse_json(current_ai1_solution)
                if temp_coords:
                    ai1_coords, ai1_matrix = temp_coords, temp_matrix
            else:
                # 解析失败了，我们保留上一轮的方案，不更新 current_ai1_solution
                add_msg("info", "💡 AI1 返回格式损坏，系统自动锁定上一轮有效方案进行后续验证。")

        except Exception as e:
            add_msg("warning", f"⚠️ AI1评估出错: {e}")
            break

    # 最终结果处理
    st.session_state.verification_messages = verification_msgs
    # 如果没达成一致，这里你可以根据需求选择返回 AI1 或 AI2 的最后结果
    return ai1_coords, ai1_matrix, False, current_ai1_solution, None, log_files