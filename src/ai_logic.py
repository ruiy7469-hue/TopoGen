"""
TopoGen: Reasoning Layer (The Brain)
This module implements the neuro-symbolic reasoning pipeline, including
multi-modal intent parsing and the Generator-Auditor negotiation protocol.
"""

import re
import json
import datetime
import os
import base64
import io
from PIL import Image
import google.generativeai as genai
import streamlit as st
from openai import OpenAI
from src.language import t


def encode_image_to_base64(image_file):
    """Converts Streamlit uploaded image to Base64 for MLLM ingestion."""
    try:
        if image_file is None:
            return None
        return base64.b64encode(image_file.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"DEBUG: Image transcoding failed: {e}")
        return None


def build_multimodal_prompt(user_text=None, has_image=False):
    """Constructs the system prompt for GIR (Graph-based Intermediate Representation) synthesis."""
    prompt_parts = []

    if has_image:
        prompt_parts.append(
            "You are a Traffic Engineering Expert specializing in extracting topological road network structures from sketches or maps. "
            "Analyze the provided visual and textual inputs to identify all intersections (nodes) and road connections (edges)."
        )
    else:
        prompt_parts.append(
            "You are a Traffic Simulation Assistant. Transform the following natural language requirements into a structured road network graph."
        )

    prompt_parts.append(
        "Please return a strict JSON object containing two fields:\n"
        "1. \"node_coordinates\": [[x1,y1], [x2,y2], ...] —— Geographic coordinates (meters).\n"
        "2. \"adjacency_matrix\": N×N array —— Directed connectivity matrix.\n\n"

        "### CRITICAL CONSTRAINTS FOR TOPOLOGICAL ANALYSIS:\n"
        "1. **Indexing Consistency**: If a node is labeled '0' in the image, its coordinates MUST be the first element (index 0) in the `node_coordinates` list.\n"
        "2. **Geometric Integrity**: Maintain relative geometric proportions as depicted in the visual input.\n"
        "3. **Connectivity**: Every node must be connected to at least one other node; isolated components are strictly forbidden.\n\n"

        "### NODE COORDINATE RULES:\n"
        "- **No Null Values**: Every element in `node_coordinates` must be a valid [x, y] pair.\n"
        "- **Numeric Precision**: Coordinates must be numerical values, not strings or null placeholders.\n\n"

        "### ADJACENCY MATRIX RULES:\n"
        "- matrix[i][j] represents a directed road from node i to node j.\n"
        "- Default to bidirectional: Set both matrix[i][j] and matrix[j][i] unless specified otherwise.\n"
        "- Element format: [speed_mps (float), num_lanes (int)], e.g., [13.9, 2].\n"
        "- Use `null` only to represent the absence of a connection.\n\n"

        "### DEFAULTS:\n"
        "- Speed: 13.9 m/s (~50 km/h) if unspecified.\n"
        "- Lanes: 1 per direction if unspecified.\n\n"

        "### EXAMPLE OUTPUT:\n"
        "{\n"
        "  \"node_coordinates\": [[0,0], [100,0], [50,87]],\n"
        "  \"adjacency_matrix\": [\n"
        "    [null, [13.9, 2], [13.9, 1]],\n"
        "    [[13.9, 2], null, [13.9, 1]],\n"
        "    [[13.9, 1], [13.9, 1], null]\n"
        "  ]\n"
        "}\n\n"

        "WARNING: Return ONLY pure JSON. Do not include markdown blocks, explanations, or verbosity. "
        "Strictly ensure `node_coordinates` contains NO null values."
    )

    if user_text:
        prompt_parts.append(f"### USER SUPPLEMENTARY REQUIREMENTS: \"{user_text}\"")
    return "\n".join(prompt_parts)


def call_llm_engine(model_brand, api_key, prompt, history=None, image_file=None):
    """Universal MLLM Engine supporting Gemini and OpenAI-compatible backbones."""
    if history is None: history = []
    temp = st.session_state.get("temp", 0.1)

    # --- Google Gemini Implementation ---
    if model_brand == "Gemini":
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        inputs = [Image.open(image_file), prompt] if image_file else prompt
        chat = model.start_chat(history=history)

        response = chat.send_message(
            inputs,
            generation_config=genai.types.GenerationConfig(temperature=temp)
        )
        return response.text.strip(), chat.history

    # --- OpenAI/Qwen/DeepSeek Implementation ---
    else:
        # Configuration for Qwen or generic OpenAI providers
        b_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        m_name = "qwen-vl-plus"

        client = OpenAI(api_key=api_key, base_url=b_url)

        # Standardizing history format for non-Gemini models
        messages = []
        for h in history:
            role = "user" if h["role"] == "user" else "assistant"
            messages.append({"role": role, "content": h["parts"][0]})

        current_content = []
        if image_file:
            base64_str = encode_image_to_base64(image_file)
            current_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_str}"}
            })
        current_content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": current_content})

        response = client.chat.completions.create(
            model=m_name,
            messages=messages,
            temperature=temp,
            stream=False
        )
        ans_text = response.choices[0].message.content
        new_history = history + [
            {"role": "user", "parts": [prompt]},
            {"role": "model", "parts": [ans_text]}
        ]
        return ans_text.strip(), new_history


def call_google_ai_vision(api_key, text_prompt=None, image_file=None):
    """Entry point for initial Generator synthesis."""
    brand = st.session_state.get("selected_model", "Gemini")
    return call_llm_engine(brand, api_key, text_prompt, image_file=image_file)


def call_ai_to_fix(api_key, history, user_feedback):
    """Handles linguistic intervention for topological refinement."""
    brand = st.session_state.get("selected_model", "Gemini")
    prompt = f"User Refinement Instruction: {user_feedback}\nUpdate the GIR (JSON) accordingly while maintaining overall topological consistency."
    return call_llm_engine(brand, api_key, prompt, history=history)


def clean_and_parse_json(raw_text):
    """Robust JSON extractor for handling LLM verbosity and markdown artifacts."""
    if not raw_text or str(raw_text).lower() == "null":
        return None, None

    try:
        # Remove potential markdown code block markers
        text = re.sub(r'```(?:json)?', '', raw_text, flags=re.IGNORECASE)
        text = text.replace('```', '').strip()

        # Isolate the outer-most JSON structure
        match = re.search(r'(\{[\s\S]*\})', text)
        if not match:
            return None, None

        json_str = match.group(1)
        data = json.loads(json_str, strict=False)

        if not data or not isinstance(data, dict):
            return None, None

        coords = data.get("node_coordinates")
        matrix = data.get("adjacency_matrix")

        # Handle nested logic in refined proposals
        if coords is None and "final_solution" in data:
            inner = data.get("final_solution")
            if isinstance(inner, dict):
                coords = inner.get("node_coordinates")
                matrix = inner.get("adjacency_matrix")

        return coords, matrix

    except Exception as e:
        print(f"DEBUG: Critical JSON parsing failure: {e}")
        return None, None


def save_ai_conversation_to_txt(agent_name, round_num, prompt, response):
    """Logs agentic reasoning traces to local storage for reproducibility."""
    log_dir = "ai_chat_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(log_dir, f"{agent_name}_Cycle{round_num}_{timestamp}.txt")

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"--- TopoGen Negotiation Trace: {agent_name} --- \n")
            f.write(f"Cycle: {round_num} | Time: {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"[PROMPT]:\n{prompt}\n\n")
            f.write(f"[RESPONSE]:\n{response}\n")
        return filename
    except Exception as e:
        print(f"DEBUG: Logging failure: {e}")
        return None


def ai_cross_verification(api_key, api_key_auditor, original_prompt, initial_proposal, image_file=None):
    """
    Implements the core Generator-Auditor Negotiation Protocol.
    This facilitates iterative refinement of the topological graph (GIR).
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

    def extract_json_from_text(text):
        """Internal helper for preference-based JSON extraction."""
        if not text: return None
        try:
            t_clean = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.IGNORECASE)
            t_clean = re.sub(r'\s*```$', '', t_clean.strip())
            match = re.search(r'(\{[\s\S]*\})', t_clean)
            json_str = match.group(1) if match else t_clean
            return json.loads(json_str, strict=False)
        except:
            if "correct" in text.lower() or "is_correct" in text.lower():
                return {"is_correct": True, "evaluation": "Implicit approval detected."}
            return None

    # --- Environment Initialization ---
    brand = st.session_state.get("selected_model", "Gemini")

    # Initialize Generator memory
    generator_history = [
        {"role": "user", "parts": [original_prompt]},
        {"role": "model", "parts": [initial_proposal]}
    ]

    current_gen_solution = initial_proposal
    last_gen_rationale = "Initial synthesis proposal."
    log_files = []
    max_rounds = 3

    gen_coords, gen_matrix = clean_and_parse_json(current_gen_solution)

    # --- Negotiation Loop ---
    for round_num in range(1, max_rounds + 1):
        add_msg("write", f"🔄 Negotiation Cycle: {round_num}/{max_rounds}")

        # ----- STEP 1: Auditor Critique -----
        gen_context = f"Generator's Previous Rationale: {last_gen_rationale}"
        audit_prompt = f"""
        You are a Traffic Engineering Auditor. Verify the road network GIR proposed by the Generator.
        ### Original Intent: {original_prompt}
        ### Generator's Proposal: {current_gen_solution}
        {gen_context}
        Audit the coordinates, adjacency logic, and lane consistency. 
        Describe the visual layout as seen in the image to verify your grounding.
        Return strict JSON: {{"is_correct": bool, "evaluation": "str", "corrected_solution": {{...}}}}
        """
        try:
            auditor_text, _ = call_llm_engine(
                brand, api_key_auditor, audit_prompt, image_file=image_file
            )

            log_file = save_ai_conversation_to_txt("Auditor", round_num, audit_prompt, auditor_text)
            if log_file: log_files.append(log_file)

            audit_result = extract_json_from_text(auditor_text)
            if audit_result is None:
                add_msg("warning", "⚠️ Auditor response corrupted. Defaulting to Generator consensus.")
                break

            if audit_result.get("is_correct", False):
                add_msg("success", "✅ Auditor Consensus Reached: Topological Integrity Verified.")
                return gen_coords, gen_matrix, True, None, None, log_files

            aud_correction = audit_result.get("corrected_solution")
            add_msg("info", f"ℹ️ Auditor Critique: {audit_result.get('evaluation', 'Structural flaws detected.')}")

        except Exception as e:
            add_msg("warning", f"⚠️ Auditor Communication Failure: {e}")
            break

        # ----- STEP 2: Generator Refinement -----
        refine_prompt = f"""
        The Auditor has identified errors in your proposal.
        ### Auditor Critique: {audit_result.get('evaluation')}
        ### Suggested Correction: {json.dumps(aud_correction)}
        Evaluate the critique. If you agree, return the corrected graph in `final_solution`. 
        If you disagree, provide your technical rationale and the intended graph.
        Return strict JSON: {{"agree": bool, "reason": "str", "final_solution": {{...}}}}
        """
        try:
            gen_refine_text, generator_history = call_llm_engine(
                brand, api_key, refine_prompt, history=generator_history
            )

            log_file = save_ai_conversation_to_txt("Generator", round_num, refine_prompt, gen_refine_text)
            if log_file: log_files.append(log_file)

            gen_refine_res = extract_json_from_text(gen_refine_text)
            if gen_refine_res is None: raise Exception("Generator response syntax error.")

            last_gen_rationale = gen_refine_res.get("reason", "Persistent structural intent.")

            if gen_refine_res.get("agree", False):
                add_msg("success", "✅ Generator accepted Auditor's refinement.")
                final = gen_refine_res.get("final_solution", aud_correction)
                return final.get("node_coordinates"), final.get("adjacency_matrix"), True, None, None, log_files

            add_msg("warning", f"⚠️ Generator Dispute: {last_gen_rationale}")
            current_gen_solution = json.dumps(gen_refine_res.get("final_solution"))
            gen_coords, gen_matrix = clean_and_parse_json(current_gen_solution)

        except Exception as e:
            add_msg("warning", f"⚠️ Generator Refinement Failure: {e}")
            break

    st.session_state.verification_messages = verification_msgs
    return gen_coords, gen_matrix, False, current_gen_solution, None, log_files