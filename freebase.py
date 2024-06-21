import re
from SPARQLWrapper import SPARQLWrapper, JSON
from prompt import relations_reduced_prompt, relations_distant_reduced_prompt
from utils import run_llm, token_count, get_list_str, timer_func
import random
import concurrent.futures


SPARQLPATH = "http://10.3.216.75:60156/sparql"  # depend on your own internal address and port
# SPARQLPATH = "http://10.3.76.30:8890/sparql"
# SPARQLPATH= "http://localhost:8890/sparql"

# pre-defined sparql
sparql_head_relations = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
ns:%s ?r ?e .
}
"""
sparql_head_relations_2hop = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
ns:%s ns:%s ?e .
?e ?r ?e1 .
FILTER(?e1 != ns:%s)
}
"""
sparql_head_relations_3hop = """
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

sparql_tail_entities = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?e
WHERE {
ns:%s ns:%s ?e .
}
LIMIT 50
""" 
# sparql_tail_entities_2hop = """
# PREFIX ns: <http://rdf.freebase.com/ns/>
# SELECT DISTINCT ?e
# WHERE {
# ns:%s ns:%s ?e0 .
# ?e0 ns:%s ?e .
# FILTER(?e != ns:%s)
# }
# """ 
sparql_entity_name = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?name
WHERE {
ns:%s ns:type.object.name ?name .
}
"""
sparql_entity_name_wiki = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?name
WHERE {
ns:%s <http://www.w3.org/2002/07/owl#sameAs> ?name .
}
"""
sparql_entity_name_literal = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?name
WHERE {
ns:%s ?r ?name .
FILTER (isLiteral(?name))
}
"""
sparql_entity_name_1hop = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?name
WHERE {
ns:%s ?r ?e . 
FILTER(?e != ns:%s)
?e ns:type.object.name ?name .
}
""" 
sparql_entity_name_extra = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r ?name
WHERE {
{
ns:%s ?r ?name .
FILTER (isLiteral(?name))
}
UNION
{
ns:%s ?r ?e . 
FILTER(?e != ns:%s)
?e ns:type.object.name ?name .
}
}
"""
sparql_entity_description = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?des
WHERE {
ns:%s ns:common.topic.description ?des .
}
"""
sparql_entity_alias = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?alias
WHERE {
ns:%s ns:common.topic.alias ?alias .
}
"""

def execute_sparql(sparql_query):
    sparql = SPARQLWrapper(SPARQLPATH)
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return results["results"]["bindings"]

# @timer_func
def get_relations(question, topic, topic_name, args, top_n):
    head_relations = execute_sparql(sparql_head_relations % topic)
    head_relations = filter_relations(head_relations)
    if len(head_relations) > top_n > 0:
        head_relations = reduce_relations(question, topic_name, head_relations, args, top_n)

    return head_relations

# @timer_func
def get_relations_distant(question, topic, topic_name, relations, paths, args, top_n):
    head_relations = {}
    for relation in relations:
        if '->' in relation:
            head_relation = execute_sparql(sparql_head_relations_3hop % (topic, relation.split('->')[0], relation.split('->')[1], topic))
        else:
            head_relation = execute_sparql(sparql_head_relations_2hop % (topic, relation, topic))
        head_relation = filter_relations(head_relation)
        if len(head_relation) > 0:
            head_relations.update({relation: {'relation': head_relation, 'fact': paths[relation]['fact']}})
    if sum([len(head_relations[r]['relation']) for r in head_relations]) > top_n > 0:
        head_relations = reduce_relations_distant(question, topic_name, head_relations, args, top_n)
    else:
        relations_list = []
        for r in  head_relations:
            for i in head_relations[r]['relation']:
                relations_list.append(r + '->' + i)
        head_relations = relations_list
    return head_relations

def filter_relations(sparql_output):
    relations = []
    for i in sparql_output:
        relation = i['r']['value']
        if relation.startswith("http://rdf.freebase.com/ns/"):
            relation = relation.replace("http://rdf.freebase.com/ns/", "")
            if not (relation.startswith(('kg', 'imdb', 'common', 'type', 'freebase')) or relation.endswith(('id', 'msrp')) or 'iso' in relation):
            # if not (relation.startswith(('kg', 'imdb', 'common', 'type', 'freebase')) or relation.endswith(('id', 'msrp', 'number', 'amount', 'permission', 'email', 'unemployment_rate', 'population'))):
                relations.append(relation)

    return relations


def reduce_relations(question, topic_name, relations, args, top_n):
    prompt = relations_reduced_prompt.format(top_n, question, topic_name, ', '.join(relations))
    # delete last 10 of the most lengthy relations if over token limits
    while token_count(prompt) > 7500:
        relations = relations[:-10]
        prompt = relations_reduced_prompt.format(top_n, question, topic_name, ', '.join(relations))
    # print(prompt)
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm, args.verbose)
    reduced_relations = get_reduced_relations(response, relations)
    minimum = max(top_n - 1, 1)
    while len(reduced_relations) < minimum:
        print('Reduced relations failed, Retrying.')
        print(response)
        response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm, args.verbose)
        reduced_relations = get_reduced_relations(response, relations)

    return reduced_relations


def reduce_relations_distant(question, topic_name, relations, args, top_n):
    prompt = relations_distant_reduced_prompt.format(top_n, question, topic_name)
    for i, r in enumerate(relations):
        prompt += '\n{}.\n1-hop relation: {}\nfact: {}\nnext relations: {}\n'.format(i+1, r.rsplit('->', 1)[-1], relations[r]['fact'], ', '.join(relations[r]['relation']))
    # delete last 10 of the most lengthy relations if over token limits
    while token_count(prompt) > 7000:
        prompt = relations_distant_reduced_prompt.format(top_n, question, topic_name)
        max_count = max([token_count(relations[r]['relation']) for r in relations])
        for i, r in enumerate(relations):
            if token_count(relations[r]['relation']) == max_count:
                relations[r].update({'relation': relations[r]['relation'][:-10]})
            prompt += '\n{}.\n1-hop relation: {}\nfact: {}\nnext relations: {}\n'.format(i+1, r.rsplit('->', 1)[-1], relations[r]['fact'], ', '.join(relations[r]['relation']))
    # print(prompt)
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm, args.verbose)
    relations_list = []
    for r in  relations:
        for i in relations[r]['relation']:
            relations_list.append(r + '->' + i)
    reduced_relations = get_reduced_relations(response, relations_list)
    minimum = max(top_n - 1, 1)
    while len(reduced_relations) < minimum:
        print('Reduced relations failed, Retrying.')
        print(response)
        response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm, args.verbose)
        reduced_relations = get_reduced_relations(response, relations_list)

    return reduced_relations

def get_reduced_relations(response, relations):
    response_list = get_list_str(response)
    exclude = str.maketrans('', '', '!"#$%&\'()*+,/:;?@[\]^`{|}~')
    response_list = [i.translate(exclude).replace(" ", "") for i in response_list if i.count('.') > 1]
    reduced_relations = []
    for relation in relations:
        if relation in response_list or relation.split('->', 1)[-1] in response_list:
        # if relation in response_list or relation.rsplit('->', 1)[-1] in [i.rsplit('->', 1)[-1] for i in response_list]:
            reduced_relations.append(relation)

    return reduced_relations



# @timer_func
def get_entities(topic, relations):
    entities_id, entities_name = [], []
    for relation in relations:
        tail_entities = execute_sparql(sparql_tail_entities % (topic, relation))
        ### !!! some relations like m.04n32 --> music.artist.track has 8477 tail entities
        tail_entities_id, tail_entities_name = filter_entities(tail_entities, topic)
        # tail_entities_id, tail_entities_name = list(set(tail_entities_id)), list(set(tail_entities_name))
        # assert len(tail_entities_id) == len(tail_entities_name), 'Entities with same name exist!'
        entities_id.append(tail_entities_id)
        entities_name.append(tail_entities_name)
    
    return entities_id, entities_name

# @timer_func
def get_entities_distant(paths, relations):
    ids, names = [], []
    for relation in relations:
        entities_id, entities_name = [], []
        topics = paths[relation.rsplit('->', 1)[0]]['entities_id']
        for topic in topics:
            tail_entities = execute_sparql(sparql_tail_entities % (topic, relation.rsplit('->', 1)[1]))
            ### !!! some relations like m.04n32 --> music.artist.track has 8477 tail entities
            tail_entities_id, tail_entities_name = filter_entities(tail_entities, topic)
            # tail_entities_id, tail_entities_name = list(set(tail_entities_id)), list(set(tail_entities_name))
            # assert len(tail_entities_id) == len(tail_entities_name), 'Entities with same name exist!'
            entities_id.append(tail_entities_id)
            entities_name.append(tail_entities_name)
        ids.append(entities_id)
        names.append(entities_name)
    return ids, names


def filter_entity(i, topic):
    entity_id = i['e']['value']
    if entity_id.startswith("http://rdf.freebase.com/ns/"):
        entity_id = entity_id.replace("http://rdf.freebase.com/ns/", "")
        entity_name = get_entity_name(entity_id, topic)
    elif i['e']['type'] in ['literal', 'typed-literal']: # text entities (has no id, no head relations)
        entity_id = i['e']['type']
        entity_name = entity_id

    return entity_id, entity_name

# def filter_entities(sparql_output, topic, remove_na=False):
#     entities_id, entities_name = [], []

#     with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
#         futures = [executor.submit(filter_entity, i, topic) for i in sparql_output]
#         for future in concurrent.futures.as_completed(futures):
#             entity_id, entity_name = future.result()
#             entities_id.append(entity_id)
#             entities_name.append(entity_name)

#     if remove_na:
#         keep_index = [i for i, name in enumerate(entities_name) if name != 'NA']
#         entities_id = [entities_id[i] for i in keep_index]
#         entities_name = [entities_name[i] for i in keep_index]

#     return entities_id, entities_name


def filter_entities(sparql_output, topic, remove_na=False):
    entities_id, entities_name = [], []
    for i in sparql_output:
        entity_id = i['e']['value']
        if entity_id.startswith("http://rdf.freebase.com/ns/"):
            entity_id = entity_id.replace("http://rdf.freebase.com/ns/", "")
            entity_name = get_entity_name(entity_id, topic)
            entities_id.append(entity_id)
            entities_name.append(entity_name)
        elif i['e']['type'] in ['literal', 'typed-literal']: # text entities (has no id, no head relations)
            entities_id.append(i['e']['type'])
            entities_name.append(entity_id)
    if remove_na:
        keep_index = [i for i, name in enumerate(entities_name) if name != 'NA']
        entities_id = [entities_id[i] for i in keep_index]
        entities_name = [entities_name[i] for i in keep_index]

    return entities_id, entities_name


def get_entity_name(entity_id, topic):
    name = execute_sparql(sparql_entity_name % entity_id)
    if len(name) == 0:
        name = execute_sparql(sparql_entity_name_wiki % entity_id) # try wiki sameas name
    
    if len(name) > 0:
        name = ", ".join([i['name']['value'] for i in name])
    else:
        name = execute_sparql(sparql_entity_name_extra % (entity_id, entity_id, topic)) # try connected literal or 1-hop entity name except original topic
        if len(name) > 0:
            name = ", ".join(["{}: {}".format(i['r']['value'].split('.')[-1], i['name']['value']) for i in name if len(filter_relations([i])) > 0])
        else: 
            name = 'NA'

    return name

