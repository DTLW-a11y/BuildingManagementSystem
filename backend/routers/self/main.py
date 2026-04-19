from data import data
from analysis import handle_question
from change import smart_ask      

question =input("请输入您的问题：")
#input函数用于获取用户输入，
# 括号内的字符串是提示信息，告诉用户应该输入什么内容。
# 当用户输入内容并按下回车键后，输入的内容将作为字符串返回，
# 并赋值给变量question。

#数据处理判断异常是通过系统规定的，之后只会给ai以异常或是相关的数据，
#所以这里要接一下数据

result=handle_question(question,data)

if result["type"]=="anomaly":
    prompt=f"""
    你是建筑能源运维专家，
    完整数据：
    {data}
    请分析以下异常数据
    {result["data"]}
    """
elif result["type"]=="advice":
    prompt=f"""
    你是建筑能源运维专家，
    请根据以下建筑能耗数据给出节能建议：
    {result["data"]}
    """
else:
    prompt="你是建筑能源运维专家，请回答用户问题" + question

answer=smart_ask(prompt)

print("最终模型分析结果：",answer)