#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd

visit_registry = pd.read_csv(
    "visit_registry.csv",
    dtype={"Patient_No": "string", "Case_No": "string"}
)

print(visit_registry.columns.tolist())


# In[2]:


raw = pd.read_excel(
    "surgery patient1-5.xlsx",
    sheet_name="Raw_Procedures",
    dtype={
        "Patient_No": "string",
        "Case_No": "string"
    }
)


# In[3]:


data = raw.merge(
    visit_registry[
        ["Patient_No", "Case_No", "visit_occurrence_id"]
    ],
    on=["Patient_No", "Case_No"],
    how="left",
    validate="many_to_one"
)


# In[4]:


print(
    data[
        ["Patient_No", "Case_No", "visit_occurrence_id"]
    ]
)


# In[ ]:




