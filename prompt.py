topic_prompt = """Given a quesion, please extract any useful information about the topic of the given question.
quesion: {}
topic: {}
information:
"""

question_prompt = """Given the background information of the topic that related to the question, please the answer the question as simple as possible and return all the possible answers as a list..

information: {}

quesion: {}
"""

relations_reduced_prompt = """Based on the question, please select the most relevant relations of the topic and just return at most {} relations as a list.

question :{}
topic: {}
relations: {}
"""

direct_propagate_prompt = """ Given the question and {} related facts of its topic, please summarize each fact while keeping anything useful to answer the question and return each summarized fact as a list.

question: {}

fact:"""