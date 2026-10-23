#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd

# 1. 读取原始 Procedures 数据
raw = pd.read_excel(
    "surgery patient1-5.xlsx",
    sheet_name="Raw_Procedures",
    dtype={"Patient_No": "string"}
)

# 2. 读取组员的患者匿名化对照表
registry = pd.read_csv(
    "person_registry.csv",
    dtype={"Patient_No": "string"}
)

# 3. 根据 Patient_No 匹配患者
data = raw.merge(
    registry[["Patient_No", "person_id", "date_offset_days"]],
    on="Patient_No",
    how="left",
    validate="many_to_one"
)

# 4. 检查有没有匹配失败
if data["date_offset_days"].isna().any():
    raise ValueError("Some patients have no date offset!")

# 5. 计算新的手术日期
data["operation_date"] = pd.to_datetime(data["operation_date"])

data["procedure_date"] = (
    data["operation_date"]
    + pd.to_timedelta(data["date_offset_days"], unit="D")
).dt.date

# 6. 查看结果
print(data[["person_id", "procedure_date"]])

