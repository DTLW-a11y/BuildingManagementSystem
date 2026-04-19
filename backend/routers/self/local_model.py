import requests 
def ask_local_model(prompt):
    res=requests.post(
         "http://localhost:11434/api/generate",
         #接口严格按照文档来写，不能有任何错误，所以要在键值中间添加空格
         json={
             "model": "qwen:7b", 
             "prompt": prompt,#写成变量，便于后续丰富功能
             "stream": False
         }
      )
    return res.json()["response"]

#只负责调用本地模型，接收数据