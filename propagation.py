from utils import run_llm, get_list_str, token_count, sort_with_indices
from prompt import *
import re


def get_propagate_list(topic_name, paths, limit):
    propagate_list = []
    for relation in paths:
        entities_name = list(set(paths[relation]['entities'][topic_name].values()))
        propagate = 'The {} has relation {} with following: {}.'.format(topic_name, relation, '; '.join(sorted(entities_name)))
        while token_count(propagate) > limit:
            entities_name = entities_name[:-10]
            propagate = 'The {} has relation {} with following: {}.'.format(topic_name, relation, '; '.join(sorted(entities_name)))
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
                propagate.append('The {} has relation {} with following: {}.'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(sorted(entities_name[i]))))
        while sum([token_count(i) for i in propagate]) > limit:
            n = n - 10
            propagate = []
            for i in range(n):
                if len(entities_name[i]) > 0:
                    propagate.append('The {} has relation {} with following: {}.'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(sorted(entities_name[i]))))
        if len(propagate) == 0:
            propagate = paths[relation.rsplit('->', 1)[0]]['fact']
        else:
            propagate = ' '.join(propagate)
        propagate_list.append(propagate)

    return propagate_list

def split_propagate_list(relations, propagate_list, limit):
    """Split propagate list in order to prevent exceeding token limits in LLM.
    """
    # sort
    propagate_list_len = [token_count(i) for i in propagate_list]
    propagate_list_len, sorted_index = sort_with_indices(propagate_list_len)
    relations = [relations[i] for i in sorted_index]
    propagate_list = [propagate_list[i] for i in sorted_index]
    # split 
    splitted_propagate_list = []
    temp_list = [propagate_list[0]]
    n_token = token_count(propagate_list[0])
    for i in range(1, len(propagate_list)):
        if n_token + propagate_list_len[i] < limit:
            temp_list.append(propagate_list[i])
            n_token += propagate_list_len[i]
        else:
            splitted_propagate_list.append(temp_list)
            temp_list = [propagate_list[i]]
            n_token = propagate_list_len[i]

    splitted_propagate_list.append(temp_list)


    return relations, splitted_propagate_list


def basic_propagate(question, prompt, facts, propagate_list, topic_name, args):
    n = len(propagate_list)
    if n == 1:
        prompt = prompt.format('', question, topic_name, facts) + propagate_list[0]
        
    else:
        prompt = prompt.format(n, question, topic_name, facts)
        for i in range(n):
            prompt += '\n{}. '.format(i+1) + propagate_list[i]
    prompt += '\n\nNote: \nSummarize while retaining the original terminology and key details.' 
    prompt += '\nYou need to summarize facts and do not repeat the facts given.' 
    if n > 1:
        prompt += '\nYou must return the same amount of facts as given.' 
    response = run_llm(prompt, args)
    output = get_list_str(response)
    if n == 1:
        output = [' '.join(output)]
    history = []
    retry_prompt = 'I only count facts in numbered list. The number of summarized facts must match with the number of given facts, which is {}. Please try again.'.format(n)
    while len(output) != n:
        print('Propagation format unmatched. Retrying...')
        history.append(response)
        response = run_llm(prompt, args, history, retry_prompt)
        output = get_list_str(response)
        
    return output


def propagate(question, topic_name, relations, paths, args):
    output = []
    if len(relations) > 0:
        if '->' in relations[0]:
            propagate_list = get_propagate_list_distant(relations, paths[topic_name], args.max_length)
            prompt = propagate_distant_prompt
            facts = '\n'.join(list(set([paths[topic_name][relation.rsplit('->', 1)[0]]['fact'] for relation in relations])))
        else:
            propagate_list = get_propagate_list(topic_name, paths[topic_name], args.max_length)
            prompt = propagate_prompt
            facts = ''

        # output = propagate_list  # remove propagation to save money if needed for openAI

        relations, propagate_list = split_propagate_list(relations, propagate_list, args.limit)
        for i in propagate_list:
            output += basic_propagate(question, prompt, facts, i, topic_name, args)

        for i, r in enumerate(relations):
            paths[topic_name][r].update({"fact": output[i]})
        


    return paths
