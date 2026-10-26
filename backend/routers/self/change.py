from .cloud_model import ask_cloud_model
from .local_model import ask_local_model
def smart_ask(prompt):
    print("尝试云模型")
    result=ask_cloud_model(prompt)

    if result is None or "云端错误" in result:
        #为啥云端错误就能简单反应问题出现
        print("云模型分析失败，尝试本地模型")
        result=ask_local_model(prompt)
        #这里应把本地的单拎出来
    else:
        print("云模型分析成功")
    return result