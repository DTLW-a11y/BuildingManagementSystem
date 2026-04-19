import requests
import os

API_KEY = os.getenv("QIANWEN_API_KEY")

def ask_cloud_model(prompt):
    print("正在调用云模型接口...")
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "qwen-turbo",
        "input": {
            "prompt": prompt
        }
    }
    """ print("status_code:",response.status_code)
    #状态码200表示请求成功，400表示请求错误，401表示未授权，403表示禁止访问，404表示未找到，500表示服务器错误等。
    print("response_text:",response.text)
    # response.text是服务器返回的响应内容，通常是一个字符串，可以是JSON格式的数据，也可以是纯文本等。
    try:
        result=response.json()
        print("云模型原始响应：", result)
        return result["output"]["text"]
    except Exception as e:
        print("云模型响应解析错误：", e)
        return "云模型响应解析错误，请稍后重试"
    """
    #三引号必须符合缩进规则，不然会报错
    
    response = requests.post(url, headers=headers, json=data)
    result=response.json()
    return result["output"]["text"]
