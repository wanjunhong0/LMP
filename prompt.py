question_prompt = """Based on the given the facts and your own knowledge, please the answer the question as simple as possible and only return all the possible answers in a numbered list. 

facts: {}
question: {}
"""

relations_reduced_prompt = """Given the question, we have the topic of the question and its relations.

question: {1}
topic: {2}

Based on the question, please select top {0} relations from the options below to explore about the topic to answer the question and just return top {0} selected relations in a numbered list without explanation.
options: {3}
"""


relations_distant_reduced_prompt = """Given the question and its topic, we have some facts about it.

question: {1}
topic: {2}

Based on the question and given facts, please only select top {0} relations from the options below to further explore about the facts to answer the question and just return top {0} selected relations in a numbered list without explanation.
"""

propagate_prompt = """Given the question, we have {0} facts about its topic and related relation that may helpful to answer the question.

question: {1}
topic: {2}
{3}
Based on the question, please summarize each following fact while only keeping every relevant information about the question and just return all summarized facts as following order in the same numbered list without explanation. 

facts:
"""


propagate_distant_prompt = """Given the question, we have {0} facts with some background information related to them and the topic.

question: {1}
topic: {2}
background information: 
{3}

Based on the question, please summarize each following fact while only keeping every relevant information about the question and just return all summarized facts as following order in the same numbered list without explanation. 

fact:
"""
