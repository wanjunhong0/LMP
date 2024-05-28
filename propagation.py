from utils import run_llm, get_list_str, token_count
from prompt import *
import re


def get_propagate_list(topic_name, relations, entities_name):
    propagate_list = []
    for i in range(len(relations)):
        propagate_list.append('The topic {} has relation {} with following entities: {}.'.format(topic_name, relations[i], '; '.join(list(set(entities_name[i])))))

    return propagate_list

def split_propagate_list(propagate_list, limit=7000):
    """Split propagate list in order to prevent exceeding token limits in LLM.
    !!! Potential Bug: every single propagate fact exceeding token limits and return empty list.
    """
    propagate_list.sort(key=token_count)
    propagate_list_len = [token_count(i) for i in propagate_list]
    splitted_propagate_list = []
    temp_list = []
    n_token = 0
    for i in range(len(propagate_list)):
        if propagate_list_len[i] >=limit:
            print('Max tokens reached in single fact propagation.')
            print(propagate_list[i])
        else:
            if n_token + propagate_list_len[i] < limit:
                temp_list.append(propagate_list[i])
                n_token += propagate_list_len[i]
            else:
                splitted_propagate_list.append(temp_list)
                temp_list = [propagate_list[i]]
                n_token = propagate_list_len[i]

    splitted_propagate_list.append(temp_list)

    return splitted_propagate_list

def basic_propagate(question, propagate_list, args):
    n = len(propagate_list)
    prompt = direct_propagate_prompt.format(n, question)
    for i in range(n):
        prompt += '\n{}. '.format(i+1) + propagate_list[i]
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
    output = get_list_str(response)
    while len(output) != n:
        print('Propagation format unmatched. Retrying...')
        response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm)
        output = get_list_str(response)
    
    return output

def propagate(question, propagation_list, args):
    output = []
    propagation_list = split_propagate_list(propagation_list)
    for i in propagation_list:
        output += basic_propagate(question, i, args)

    return output

# def direct_propagate(question, topic_name, relations, entities_name, args):
#     n = len(relations)
#     prompt = direct_propagate_prompt.format(n, question)
#     for i in range(n):
#         prompt += '\n{}. the topic {} has relation {} with following entities: {}.'.format(i+1, topic_name, relations[i], '; '.join(list(set(entities_name[i]))))
#     response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
#     output = get_list_str(response)
#     while len(output) != n:
#         print('Propagation format unmatched. Retrying...')
#         print(response)
#         response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm)
#         output = get_list_str(response)
    
#     return output