from SPARQLWrapper import SPARQLWrapper, JSON
from prompts import sample_relations_prompt, sample_relations_distant_prompt
from utils import run_llm, token_count, get_list_str
import time


SPARQLPATH = "http://10.1.25.43:8890/sparql"  # depend on your own internal address and port
# SPARQLPATH= "http://localhost:8890/sparql"

# pre-defined sparql
sparql_relations = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
ns:%s ?r ?e .
}
"""
sparql_relations_2hop = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
ns:%s ns:%s ?e .
?e ?r ?e1 .
FILTER(?e1 != ns:%s)
}
"""
sparql_relations_3hop = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
ns:%s ns:%s ?e .
?e ns:%s ?e1 .
?e1 ?r ?e2 .
FILTER(?e1 != ns:%s)
FILTER(?e != ?e2)
}
"""
sparql_entities = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?start ?e ?name ?r ?e1 ?extra
WHERE {
VALUES ?start {%s}
?start ns:%s ?e .
FILTER(?e != ns:%s)
OPTIONAL {?e ns:type.object.name ?name .}.
OPTIONAL 
{FILTER (!BOUND(?name))
{?e ?r ?extra . FILTER (isLiteral(?extra))}
UNION
{?e ?r ?e1 . ?e1 ns:type.object.name ?extra . }
} .
}
LIMIT 500
""" 
sparql_entity_description = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?des
WHERE {
ns:%s ns:common.topic.description ?des .
}
"""


def execute_sparql(sparql_query: str) -> list:
    """ Execute SPARQL query"""
    sparql = SPARQLWrapper(SPARQLPATH)
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    results = None
    while results == None:
        try:
            results = sparql.query().convert()
        except:
            time.sleep(10)
    return results["results"]["bindings"]


def filter_relations(sparql_output: str) -> list:
    """ Get relations from SPARQL while removing pre-defined meaningless relations. """
    relations = []
    for i in sparql_output:
        relation = i['r']['value']
        if relation.startswith("http://rdf.freebase.com/ns/"):
            relation = relation.replace("http://rdf.freebase.com/ns/", "")
            if not (relation.startswith(('kg', 'imdb', 'common', 'type', 'freebase')) or relation.endswith(('id', 'msrp'))):
                relations.append(relation)

    return relations

def sample_relations(question: str, topic_name: str, relations: list, args) -> list:
    """ Sampling K relevant relations from 1-hop relations using LLM. """
    prompt = sample_relations_prompt.format(args.width, question, topic_name, ', '.join(relations))
    # delete the last most lengthy relations if over token limits
    while token_count(prompt) > args.limit_llm_in:
        relations = relations[:-1]
        prompt = sample_relations_prompt.format(args.width, question, topic_name, ', '.join(relations))
    prompt += '\n\nOnly return relations from the ones in the options given.'
    response = run_llm(prompt, args)
    sampled_relations = get_sampled_relations(response, relations)
    # retry if failed at retrieving K relations
    minimum = max(args.width, 1)
    history = []
    retry_prompt = 'Selected relations do not exist in the options I provide. Please try again.'
    while (len(sampled_relations) < minimum and len(history) < args.max_retry):
        print('Sampling failed, Retrying.')
        minimum = max(minimum - 1, 1)
        history.append(response)
        response = run_llm(prompt, args, history, retry_prompt)
        sampled_relations = list(set(sampled_relations + get_sampled_relations(response, relations)))

    return sampled_relations

def sample_relations_distant(question: str, topic_name: str, relations: dict, args) -> list:
    """ Sampling K relevant relations from relations beyond 1-hop using LLM. """
    prompt = sample_relations_distant_prompt.format(args.width, question, topic_name)
    for i, r in enumerate(relations):
        prompt += '\n{}.\nfact: {}\noptions: {}\n'.format(i+1, relations[r]['fact'], ', '.join(relations[r]['relation']))
    # delete the last most lengthy relations if over token limits
    while token_count(prompt) > args.limit_llm_in:
        prompt = sample_relations_distant_prompt.format(args.width, question, topic_name)
        max_count = max([token_count(relations[r]['relation']) for r in relations])
        if max_count == 0:
            raise ValueError("The facts exceed LLM token limit.")
        for i, r in enumerate(relations):
            if token_count(relations[r]['relation']) == max_count:
                relations[r].update({'relation': relations[r]['relation'][:-1]})
            prompt += '\n{}.\nfact: {}\noptions: {}\n'.format(i+1, relations[r]['fact'], ', '.join(relations[r]['relation']))
    prompt += '\n\nOnly return relations from the ones in the options given.'
    response = run_llm(prompt, args)
    relations_list = []
    for r in  relations:
        for i in relations[r]['relation']:
            relations_list.append(r + '->' + i)
    sampled_relations = get_sampled_relations(response, relations_list)
    # retry if failed at retrieving K relations
    minimum = max(args.width, 1)
    history = []
    retry_prompt = 'Selected relations do not exist in the options I provide. Please try again.'
    while (len(sampled_relations) < minimum and len(history) < args.max_retry):
        minimum = max(minimum - 1, 1)
        print('Sampling failed, Retrying.')
        history.append(response)
        response = run_llm(prompt, args, history, retry_prompt)
        sampled_relations = list(set(sampled_relations + get_sampled_relations(response, relations_list)))

    return sampled_relations

def get_sampled_relations(response: str, relations: list) -> list:
    """ Retrieve sampled relations from the output of LLM. """
    response_list = get_list_str(response)
    response_list = [i for i in ' '.join(response_list).split() if i.count('.') > 1]
    exclude = str.maketrans('', '', '!"#$%&\'()*+,/:;?@[\]^`{|}~')
    response_list = [i.translate(exclude) for i in response_list]
    sampled_relations = []
    for relation in relations:
        if relation in response_list or relation.rsplit('->', 1)[-1] in response_list:
            sampled_relations.append(relation)

    return sampled_relations


def get_relations(question: str, topic: str, topic_name: str, args) -> list:
    """ Get K topic-related 1-hop relations. """
    relations = execute_sparql(sparql_relations % topic)
    relations = filter_relations(relations)
    if len(relations) > args.width > 0:
        relations = sample_relations(question, topic_name, relations, args)

    return relations


def get_relations_distant(question: str, topic: str, topic_name: str, relations: list, graphs: dict, args) -> list:
    """ Get K topic-related relations beyond 1-hop. """
    next_relations = {}
    for relation in relations:
        if '->' in relation:
            next_relation = execute_sparql(sparql_relations_3hop % (topic, relation.split('->')[0], relation.split('->')[1], topic))
        else:
            next_relation = execute_sparql(sparql_relations_2hop % (topic, relation, topic))
        next_relation = filter_relations(next_relation)
        if len(next_relation) > 0:
            next_relations.update({relation: {'relation': next_relation, 'fact': graphs[relation]['fact']}})
    if sum([len(next_relations[r]['relation']) for r in next_relations]) > args.width > 0:
        next_relations = sample_relations_distant(question, topic_name, next_relations, args)
    else:
        relations_list = []
        for r in  next_relations:
            for i in next_relations[r]['relation']:
                relations_list.append(r + '->' + i)
        next_relations = relations_list

    return next_relations



def filter_entities(start_entities, sparql_output, args):
    """ Get entity names from SPARQL. """
    r_previous, entity_id_previous = '', ''
    entities = {start_entities[start_entity]: {} for start_entity in start_entities}
    for i in sparql_output:
        start_entity_id = i['start']['value'].replace("http://rdf.freebase.com/ns/", "")
        start_entity_name = start_entities[start_entity_id]
        if i['e']['type'] == 'uri':
            entity_id = i['e']['value'].replace("http://rdf.freebase.com/ns/", "")
            entity_name = 'NA'
            if 'name' in i:
                entity_name = i['name']['value']
            # use neighbor information for unnamed entities
            elif 'extra' in i:
                # filter useless extra relations
                r = i['r']['value'].replace("http://rdf.freebase.com/ns/", "")
                if r.endswith(('id', 'has_no_value', 'has_value')):
                    continue
                # filter entities back to start entities
                if 'e1' in i:
                    if i['e1']['value'].replace("http://rdf.freebase.com/ns/", "") in start_entities:
                        continue
                # only use one entity name per relation
                if r == r_previous and entity_id == entity_id_previous:  
                    continue
                # limit tokens
                if token_count(entity_name) > args.limit_fact:
                    continue
                if entity_id in entities[start_entity_name]:
                    entity_name = entities[start_entity_name][entity_id][:-1] + ', '
                else:
                    entity_name = 'unnamed entity with relevant information ('
                content = "{}: {}".format(r.split('.')[-1], i['extra']['value'])
                if content not in entity_name:
                    entity_name += content + ')'
                r_previous, entity_id_previous = r, entity_id
        elif i['e']['type'] in ['literal', 'typed-literal']: # text entities (has no id, no head relations)
            entity_id = i['e']['type']
            entity_name = i['e']['value']
    
        entities[start_entity_name].update({entity_id: entity_name})


    return entities


def get_entities(start_entities: dict, relations: list, topic: str, args) -> list:
    """ Get 1-hop neighbor entity names of the topic entity. """
    entities = []
    for relation in relations:
        sparql_output = execute_sparql(sparql_entities % (' '.join(['ns:' + i for i in list(start_entities.keys())]), relation, topic))
        filtered_entities = filter_entities(start_entities, sparql_output, args)
        for i in filtered_entities:
            filtered_entities[i] = dict(sorted(filtered_entities[i].items(), key=lambda item: item[1]))

        entities.append(filtered_entities)
    
    return entities


def get_entities_distant(graphs: dict, relations: list, topic: str, args) -> list:
    """ Get beyond 1-hop neighbor entity names of the topic entity . """
    entities = []
    for relation in relations:
        start_entities = {}
        previous_entities = graphs[relation.rsplit('->', 1)[0]]['entities']
        for i in previous_entities:
            for j in previous_entities[i]:
                if j not in ['literal', 'typed-literal']:  # remove start entity that does not have neighbors
                    start_entities.update({j: previous_entities[i][j]})

        sparql_output = execute_sparql(sparql_entities % (' '.join(['ns:' + i for i in list(start_entities.keys())]), relation.rsplit('->', 1)[1], topic))
        filtered_entities = filter_entities(start_entities, sparql_output, args)
        for i in filtered_entities:
            filtered_entities[i] = dict(sorted(filtered_entities[i].items(), key=lambda item: item[1]))

        entities.append(filtered_entities)
    
    return entities
