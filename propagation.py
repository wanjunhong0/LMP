from utils import run_llm, get_list_str
from prompt import *
import re

def direct_propagate(question, topic_name, relations, entities_name, args):
    n = len(relations)
    line_breaks = ['\n{}. '.format(i+1) for i in range(n)]
    prompt = direct_propagate_prompt.format(n, question)
    for i in range(len(relations)):
        prompt += '{}the topic {} has relation {} with following entities {}. '.format(line_breaks[i], topic_name, relations[i], list(set(entities_name[i])))
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
    while re.findall(r'\n[0-99]. ', response) != line_breaks:
        print('Propagation format unmatched. Retrying...')
        print(response)
        response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm)
    
    output = get_list_str(response)
    
    return output