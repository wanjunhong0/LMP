from utils import run_llm, get_list_str
from prompt import *
import re


def propagate(question, topic_name, relations, entities_name, args):
    n = len(relations)
    prompt = direct_propagate_prompt.format(n, question)
    for i in range(n):
        prompt += '\n{}. the topic {} has relation {} with following entities {}. '.format(i+1, topic_name, relations[i], '; '.join(list(set(entities_name[i]))))
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
    output = get_list_str(response)
    while len(output) != n:
        print('Propagation format unmatched. Retrying...')
        print(response)
        response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm)
        output = get_list_str(response)
    
    return output


def direct_propagate(question, topic_name, relations, entities_name, args):
    n = len(relations)
    prompt = direct_propagate_prompt.format(n, question)
    for i in range(n):
        prompt += '\n{}. the topic {} has relation {} with following entities {}. '.format(i+1, topic_name, relations[i], '; '.join(list(set(entities_name[i]))))
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
    output = get_list_str(response)
    while len(output) != n:
        print('Propagation format unmatched. Retrying...')
        print(response)
        response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm)
        output = get_list_str(response)
    
    return output