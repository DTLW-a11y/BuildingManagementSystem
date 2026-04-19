from datetime import datetime


def time_summery(data,metric="power"):
    groups={}
    result=[]
    #声明字典和列表，但是都为空，之后需要利用循环和append（）往里面填值
    #groups是一个字典，用于存储每个小时的指标值
    #key是小时，value是一个列表，用于存储该小时的指标值

    for item in data:
        #从data列表里一条一条取数据（item是一个字典，并不一定非要用item，只是最常见，别人一看就懂）
        time_str=item["time"]
        dt=datetime.strptime(time_str,"%Y-%m-%d %H:%M")
        #strptime函数用于将字符串转换为datetime对象
        #分别对应年月日小时分钟
        hour=dt.hour
        if hour not in groups:
            #每次处理这个小时的第一条数据时，
            #没有这个小时的列表，所以创建一个空字典
            groups[hour]=[]
            #表示访问键为hour的一项，=[]将其赋值为空列表
            #合起来是：创建一个新的类，并创建一个新列表
        groups[hour].append(item[metric])
    for hour in groups:   
        values=groups[hour]
        #values是列表，groups[hour]是列表,
        #用values接值，能使得原有数据不被覆盖
        avg=sum(values)/len(values)
        result.append(
            {
                "hour":hour,
                #因为这里的hour是循环对象
                "avg":avg
            }
        )#要让对外输出的格式为列表，方便之后的可视化操作
    return result
            