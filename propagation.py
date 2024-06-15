from utils import run_llm, get_list_str, token_count
from prompt import *
import re


def get_propagate_list(topic_name, paths):
    propagate_list = []
    for relation in paths:
        entities_name = list(set(paths[relation]['entities_name']))
        propagate = 'The topic {} has relation {} with following entities: [{}].'.format(topic_name, relation, '; '.join(entities_name))
        while token_count(propagate) > 7000:
            entities_name = entities_name[:-10]
            propagate = 'The topic {} has relation {} with following entities: [{}].'.format(topic_name, relation, '; '.join(entities_name))
        propagate_list.append(propagate)

    return propagate_list

def get_propagate_list_distant(relations, paths):
    propagate_list = []
    for relation in relations:
        entities_name_previous = paths[relation.rsplit('->', 1)[0]]['entities_name']
        entities_name = paths[relation]['entities_name']
        assert len(entities_name_previous) == len(entities_name), 'Entities does not match with neighbors'
        n = len(entities_name_previous)
        propagate = []
        for i in range(n):
            if len(entities_name[i]) > 0:
                propagate.append('The topic {} has relation {} with following entities: [{}].'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(entities_name[i])))
        propagate = list(set(propagate))
        while sum([token_count(i) for i in propagate]) > 7000:
            n = n - 10
            propagate = []
            for i in range(n):
                if len(entities_name[i]) > 0:
                    propagate.append('The topic {} has relation {} with following entities: [{}].'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(entities_name[i])))
            propagate = list(set(propagate))
        propagate = ' '.join(propagate)
        propagate = '\nPrevious summarized fact: {}\nNew detailed fact: {}\n'.format(paths[relation.rsplit('->', 1)[0]]['fact'], propagate)
        propagate_list.append(propagate)

    return propagate_list

def split_propagate_list(propagate_list, limit=7000):
    """Split propagate list in order to prevent exceeding token limits in LLM.
    """
    # propagate_list.sort(key=token_count)
    propagate_list_len = [token_count(i) for i in propagate_list]
    splitted_propagate_list = []
    temp_list = []
    n_token = 0
    for i in range(len(propagate_list)):
        if n_token + propagate_list_len[i] < limit:
            temp_list.append(propagate_list[i])
            n_token += propagate_list_len[i]
        else:
            splitted_propagate_list.append(temp_list)
            temp_list = [propagate_list[i]]
            n_token = propagate_list_len[i]

    splitted_propagate_list.append(temp_list)

    return splitted_propagate_list

def basic_propagate(question, propagate_list, hop, args):
    n = len(propagate_list)
    if hop > 1:
        prompt = propagate_distant_prompt.format(n, question)
    else:
        prompt = propagate_prompt.format(n, question)
    for i in range(n):
        prompt += '\n{}. '.format(i+1) + propagate_list[i]
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm, args.verbose)
    # print(prompt)
    # print(response)
    output = get_list_str(response)
    while len(output) != n:
        print('Propagation format unmatched. Retrying...')
        print(response)
        response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm, args.verbose)
        output = get_list_str(response)
    
    return output

def propagate(question, topic_name, relations, paths, hop, args):
    output = []
    if len(relations) > 0:
        if hop > 1:
            propagate_list = get_propagate_list_distant(relations, paths)
        else:
            propagate_list = get_propagate_list(topic_name, paths)
        propagate_list = split_propagate_list(propagate_list)
        for i in propagate_list:
            output += basic_propagate(question, i, hop, args)

    return output
