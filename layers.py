from utils import run_llm, get_list_str, token_count, sort_with_indices
from prompts import transformation_prompt, transformation_distant_prompt


def aggregation(topic_name: str, graphs: dict, limit: int) -> list:
    """ Aggregate 1-hop neighbor entities of the topic entity. """
    aggregation_list = []
    for relation in graphs:
        entities_name = list(set(graphs[relation]['entities'][topic_name].values()))
        aggregation = 'The entity {} has relation {} with following entities: {}.'.format(topic_name, relation, '; '.join(sorted(entities_name)))
        while token_count(aggregation) > limit:   # remove one neighbor entities if exceed limits
            entities_name = entities_name[:-1]
            aggregation = 'The entity {} has relation {} with following entities: {}.'.format(topic_name, relation, '; '.join(sorted(entities_name)))
        aggregation_list.append(aggregation)

    return aggregation_list


def aggregation_distant(relations: list, graphs: dict, limit: int) -> list:
    """ Aggregate beyond 1-hop neighbor entities of the topic entity. """
    aggregation_list = []
    for relation in relations:
        entities = graphs[relation]['entities']
        entities_name_previous = list(entities.keys())
        entities_name = [list(set(entities[i].values())) for i in entities_name_previous]
        assert len(entities_name_previous) == len(entities_name), 'Entities does not match with neighbors'
        n = len(entities_name_previous)
        aggregation = []
        for i in range(n):
            if len(entities_name[i]) > 0:
                aggregation.append('The entity {} has relation {} with following entities: {}.'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(sorted(entities_name[i]))))
        while sum([token_count(i) for i in aggregation]) > limit:   # remove one neighbor entities if exceed limits
            n = n - 1
            aggregation = []
            for i in range(n):
                if len(entities_name[i]) > 0:
                    aggregation.append('The entity {} has relation {} with following entities: {}.'.format(entities_name_previous[i], relation.rsplit('->', 1)[1], '; '.join(sorted(entities_name[i]))))
        if len(aggregation) == 0:   # repeat previous facts if no neighborhoods in current depths
            aggregation = graphs[relation.rsplit('->', 1)[0]]['fact']
        else:
            aggregation = ' '.join(aggregation)
        aggregation_list.append(aggregation)

    return aggregation_list


def split_aggregation_list(relations: list, aggregation_list: list, limit: int) -> tuple[list, list]:
    """Split aggregation list in order to prevent exceeding token limits in LLM. """
    # sort
    aggregation_len_list = [token_count(i) for i in aggregation_list]
    aggregation_len_list, sorted_index = sort_with_indices(aggregation_len_list)
    relations = [relations[i] for i in sorted_index]
    aggregation_list = [aggregation_list[i] for i in sorted_index]
    # split 
    splitted_aggregation_list = []
    temp_list = [aggregation_list[0]]
    n_token = token_count(aggregation_list[0])
    for i in range(1, len(aggregation_list)):
        if n_token + aggregation_len_list[i] < limit:
            temp_list.append(aggregation_list[i])
            n_token += aggregation_len_list[i]
        else:
            splitted_aggregation_list.append(temp_list)
            temp_list = [aggregation_list[i]]
            n_token = aggregation_len_list[i]
    splitted_aggregation_list.append(temp_list)

    return relations, splitted_aggregation_list


def transformation(question: str, prompt: str, facts: str, propagate_list: list, topic_name: str, args) -> list:
    """ Summarize aggregated neighborhood information into facts. """
    n = len(propagate_list)
    if n == 1:
        prompt = prompt.format('', question, topic_name, facts) + propagate_list[0]
        
    else:
        prompt = prompt.format(n, question, topic_name, facts)
        for i in range(n):
            prompt += '\n{}. '.format(i+1) + propagate_list[i]
    prompt += '\n\nNote:'
    prompt += '\nYou need to summarize while using the exact wording from the given facts.' 
    prompt += '\nYou need to summarize given facts with topic into meaningful sentence.' 
    if n > 1:
        prompt += '\nYou must return the same amount of facts as given.' 
    response = run_llm(prompt, args)
    output = get_list_str(response)
    if n == 1:
        output = [' '.join(output)]
    # retry if fail at returning the same amount of given facts
    history = []
    retry_prompt = 'The number of summarized facts must match with the number of given facts, which is {}. Please try again.'.format(n)
    while len(output) != n:
        print('Transformation format unmatched. Retrying...')
        history.append(response)
        response = run_llm(prompt, args, history, retry_prompt)
        output = get_list_str(response)
        if len(history) >= args.max_retry:
            output = output + [''] * (n-len(output))
        
    return output


def message_passing(question: str, topic_name: str, relations: list, graphs: dict, args) -> dict:
    """ Aggregate neighborhood information and transform into facts. """
    output = []
    if len(relations) > 0:
        if '->' in relations[0]:
            aggregation_list = aggregation_distant(relations, graphs[topic_name], args.limit_fact)
            prompt = transformation_distant_prompt
            facts = '\n'.join(list(set([graphs[topic_name][relation.rsplit('->', 1)[0]]['fact'] for relation in relations])))
        else:
            aggregation_list = aggregation(topic_name, graphs[topic_name], args.limit_fact)
            prompt = transformation_prompt
            facts = ''
            
        output = aggregation_list  # use raw aggregated information without transformation to save money if needed

        relations, aggregation_list = split_aggregation_list(relations, aggregation_list, args.limit_llm_in-args.limit_llm_out)
        for i in aggregation_list:
            output += transformation(question, prompt, facts, i, topic_name, args)

        for i, r in enumerate(relations):
            graphs[topic_name][r].update({"fact": output[i]})
            # graphs[topic_name][r].update({"fact": output[i] + '\n' + [item for sublist in aggregation_list for item in sublist][i]})  # include raw aggregated information, used for simpleqa since it only validates one random answer from multiple correct answers
        
    return graphs
