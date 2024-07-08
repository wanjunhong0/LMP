from utils import run_llm, get_list_str, token_count, timer_func
from prompt import *
import re


def get_propagate_list(topic_name, paths, limit):
    propagate_list = []
    for relation in paths:
        entities_name = list(set(paths[relation]['entities'][topic_name].values()))
        propagate = 'The topic {} has relation {} with following entities: [{}].'.format(topic_name, relation, '; '.join(entities_name))
        while token_count(propagate) > limit:
            entities_name = entities_name[:-10]
            propagate = 'The topic {} has relation {} with following entities: [{}].'.format(topic_name, relation, '; '.join(entities_name))
        propagate_list.append(propagate)

    return propagate_list

def get_propagate_list_distant(relations, paths, limit):
    propagate_list = []
    for relation in relations:
        entities = paths[relation]['entities']
        entities_name_previous = list(entities.keys())
        entities_name = [list(set(entities[i].values())) for i in entities_name_previous]
        assert len(entities_name_previous) == len(entities_name), 'Entities does not match with neighbors'
        n = len(entities_name_previous)
        propagate = []
        for i in range(n):
            if len(entities_name[i]) > 0:
                propagate.append('The entity {} has relation {} with following entities: [{}].'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(entities_name[i])))
        propagate = list(set(propagate))
        while sum([token_count(i) for i in propagate]) > limit:
            n = n - 10
            propagate = []
            for i in range(n):
                if len(entities_name[i]) > 0:
                    propagate.append('The entity {} has relation {} with following entities: [{}].'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(entities_name[i])))
            propagate = list(set(propagate))
        propagate = ' '.join(propagate)
        propagate = '\nPrevious summarized fact about the topic: {}\nNew detailed fact: {}\n'.format(paths[relation.rsplit('->', 1)[0]]['fact'], propagate)
        propagate_list.append(propagate)

    return propagate_list

def split_propagate_list(propagate_list, limit):
    """Split propagate list in order to prevent exceeding token limits in LLM.
    """
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

def basic_propagate(question, propagate_list, topic_name, hop, args):
    n = len(propagate_list)
    if hop > 1:
        prompt = propagate_distant_prompt.format(n, question, topic_name)
    else:
        prompt = propagate_prompt.format(n, question, topic_name)
    for i in range(n):
        prompt += '\n{}. '.format(i+1) + propagate_list[i]
    response = run_llm(prompt, args)
    output = get_list_str(response)
    history = []
    retry_prompt = 'The number of summarized facts must match with the number of given facts, which is {}. Please try again.'.format(n)
    while len(output) != n:
        print('Propagation format unmatched. Retrying...')
        history.append(response)
        response = run_llm(prompt, args, history, retry_prompt)
        output = get_list_str(response)
    
    return output

# @timer_func
def propagate(question, topic_name, relations, paths, hop, args):
    output = []
    if len(relations) > 0:
        if hop > 1:
            propagate_list = get_propagate_list_distant(relations, paths, args.limit)
        else:
            propagate_list = get_propagate_list(topic_name, paths, args.limit)
        propagate_list = split_propagate_list(propagate_list, args.limit)
        for i in propagate_list:
            output += basic_propagate(question, i, topic_name, hop, args)

    return output
