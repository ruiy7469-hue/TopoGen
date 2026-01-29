import os
import base64
from openai import OpenAI

# ==========================================
# 1. 清理环境（防止代理软件干扰 API 连接）
# ==========================================
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

# ==========================================
# 2. 配置你的 API 信息
# ==========================================
# 请把下面的 sk-xxxx 换成你自己的阿里云百炼 API Key
YOUR_API_KEY = "sk-aa37f590e7c04931a2825c4ed09e0809"

client = OpenAI(
    api_key=YOUR_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


# ==========================================
# 3. 本地图片转 Base64 的辅助函数
# ==========================================
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# ==========================================
# 4. 执行测试
# ==========================================
def test_qwen_vision():
    # 图片路径（确保文件存在）
    img_path = f"F:/学习/大四/毕业设计/pythonProject4/1.jpg"

    if not os.path.exists(img_path):
        print(f"❌ 错误：找不到图片文件 {img_path}，请修改文件名或放置图片。")
        return

    print("🚀 正在转码图片并发送请求...")
    base64_image = encode_image(img_path)

    try:
        completion = client.chat.completions.create(
            model="qwen3-vl-flash",  # 必须使用带 VL 的模型才能看图
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                        {"type": "text", "text": "先告诉我你是什么大模型，能看见图片吗，再告诉我图中描绘的是什么景象？请简单描述。"},
                    ],
                }
            ],
        )
        # 打印 AI 的回复
        print("\n🤖 千问的回答：")
        print(completion.choices[0].message.content)

    except Exception as e:
        print(f"\n❌ 调用失败，错误信息如下：\n{e}")


if __name__ == "__main__":
    test_qwen_vision()