question_prompt = """Based on the given the facts and your own knowledge, please the answer the question as simple as possible and return all the possible answers in a numbered list.

information: {}
question: {}
"""

relations_reduced_prompt = """Given the question, we have the topic of the question and its relations.

question: {1}
topic: {2}

Based on the question and its topic, please select the most relevant relations to answer the question from below and just return top {0} relations in a numbered list without explanation.
relations: {3}
"""

relations_distant_reduced_prompt = """Given the question and its topic, each fact is associated with the 1-hop relation about the topic.

question: {1}
topic: {2}

Based on the question and its existing facts about the topic, please select top {0} 2-hop relations to further explore that could be helpful to answer the question from below and just return selected 2-hop relations in a numbered list without explanation.
"""

propagate_prompt = """Given the question, we have {0} facts about its topic and related relation that may helpful to answer the question.

question: {1}

Based on the question, please summarize each following fact to better answer question and just return all summarized {0} facts as following order in a numbered list. 
"""

# propagate_distant_prompt = """Given the question, we have {0} previously summarized facts with some new detailed information about them.

# question: {1}

# Based on the question and added information, please re-summarize each following fact to better answer question and just return all summarized {0} facts as following order in a numbered list. 
# """

propagate_distant_prompt = """Given the question, we have some new detailed facts about {0} previously summarized facts.

question: {1}

Based on the question and previously summarized facts, please summarize each following new detailed fact to better answer question and just return all summarized {0} facts as following order in a numbered list. 
"""
# direct_propagate_prompt = """ Given the question and {0} facts of its topic, please summarize each fact while keeping anything useful to answer the question and just return all {0} summarized facts as a list.

# question: {1}

# fact:
# """