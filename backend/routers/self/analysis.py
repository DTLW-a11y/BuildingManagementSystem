def find_anomaly(data):
    anomalies = []

    for i in range(1, len(data)):
        prev = data[i-1]["power"]
        curr = data[i]["power"]

        # 超过30%算异常
        if curr > prev * 1.3:
            anomalies.append(data[i])

    return anomalies


def handle_question(question, data):

    if "异常" in question:
        anomalies = find_anomaly(data)
        return {"type": "anomaly", "data": anomalies}
    elif "建议" in question:
        return {"type": "advice", "data": data}
    else:
        return {"type": "unknown", "data": data}
    
    #为什么要用这样的格式？
    # 因为想要把不同类型的结果区分开来，
    # 而且还得对应类型返回不同的数据，
    # 所以就得要有能存储类型和数据的变量，
    # 列表中的每个元素都是一个字典，字典中包含type和data两个键值对