import re
from SPARQLWrapper import SPARQLWrapper, JSON
from prompt import relations_reduced_prompt, relations_distant_reduced_prompt
from utils import run_llm, token_count, get_list_str
import random
import concurrent.futures
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
SELECT DISTINCT ?start ?e ?name ?wiki ?r ?e1 ?extra
WHERE {
VALUES ?start {%s}
?start ns:%s ?e .
FILTER(?e != ns:%s)
OPTIONAL {?e ns:type.object.name ?name .}.
OPTIONAL {?e <http://www.w3.org/2002/07/owl#sameAs> ?wiki . FILTER (!BOUND(?name))}.
OPTIONAL 
{FILTER (!BOUND(?name) && !BOUND(?wiki))
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
    results = None
    while results == None:
        try:
            results = sparql.query().convert()
        except:
            time.sleep(10)
    return results["results"]["bindings"]


def filter_relations(sparql_output):
    relations = []
    for i in sparql_output:
        relation = i['r']['value']
        if relation.startswith("http://rdf.freebase.com/ns/"):
            relation = relation.replace("http://rdf.freebase.com/ns/", "")
            if not (relation.startswith(('kg', 'imdb', 'common', 'type', 'freebase')) or relation.endswith(('id', 'msrp'))):
                relations.append(relation)

    return relations

def reduce_relations(question, topic_name, relations, args):
    prompt = relations_reduced_prompt.format(args.width, question, topic_name, ', '.join(relations))
    # delete last 10 of the most lengthy relations if over token limits
    while token_count(prompt) > args.limit:
        relations = relations[:-10]
        prompt = relations_reduced_prompt.format(args.width, question, topic_name, ', '.join(relations))
    prompt += '\n\nOnly return relations from the ones in the options given.'
    response = run_llm(prompt, args)
    reduced_relations = get_reduced_relations(response, relations)
    minimum = max(args.width, 1)
    history = []
    retry_prompt = 'Selected relations do not exist in the options I provide. Please try again.'
    while (len(reduced_relations) < minimum and len(history) < args.max_retry):
        print('Reduced relations failed, Retrying.')
        minimum = max(minimum - 1, 1)
        history.append(response)
        response = run_llm(prompt, args, history, retry_prompt)
        reduced_relations = list(set(reduced_relations + get_reduced_relations(response, relations)))

    return reduced_relations

def reduce_relations_distant(question, topic_name, relations, args):
    prompt = relations_distant_reduced_prompt.format(args.width, question, topic_name)
    for i, r in enumerate(relations):
        prompt += '\n{}.\nfact: {}\noptions: {}\n'.format(i+1, relations[r]['fact'], ', '.join(relations[r]['relation']))
    # delete last 10 of the most lengthy relations if over token limits
    while token_count(prompt) > args.limit:
        prompt = relations_distant_reduced_prompt.format(args.width, question, topic_name)
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
    reduced_relations = get_reduced_relations(response, relations_list)
    minimum = max(args.width, 1)
    history = []
    retry_prompt = 'Selected relations do not exist in the options I provide. Please try again.'
    while (len(reduced_relations) < minimum and len(history) < args.max_retry):
        minimum = max(minimum - 1, 1)
        print('Reduced relations failed, Retrying.')
        history.append(response)
        response = run_llm(prompt, args, history, retry_prompt)
        reduced_relations = list(set(reduced_relations + get_reduced_relations(response, relations_list)))

    return reduced_relations

def get_reduced_relations(response, relations):
    response_list = get_list_str(response)
    response_list = [i for i in ' '.join(response_list).split() if i.count('.') > 1]
    exclude = str.maketrans('', '', '!"#$%&\'()*+,/:;?@[\]^`{|}~')
    response_list = [i.translate(exclude) for i in response_list]
    reduced_relations = []
    for relation in relations:
        if relation in response_list or relation.rsplit('->', 1)[-1] in response_list:
            reduced_relations.append(relation)

    return reduced_relations


def get_relations(question, topic, topic_name, args):
    relations = execute_sparql(sparql_relations % topic)
    relations = filter_relations(relations)
    if len(relations) > args.width > 0:
        relations = reduce_relations(question, topic_name, relations, args)

    return relations


def get_relations_distant(question, topic, topic_name, relations, paths, args):
    next_relations = {}
    for relation in relations:
        if '->' in relation:
            next_relation = execute_sparql(sparql_relations_3hop % (topic, relation.split('->')[0], relation.split('->')[1], topic))
        else:
            next_relation = execute_sparql(sparql_relations_2hop % (topic, relation, topic))
        next_relation = filter_relations(next_relation)
        if len(next_relation) > 0:
            next_relations.update({relation: {'relation': next_relation, 'fact': paths[relation]['fact']}})
    if sum([len(next_relations[r]['relation']) for r in next_relations]) > args.width > 0:
        next_relations = reduce_relations_distant(question, topic_name, next_relations, args)
    else:
        relations_list = []
        for r in  next_relations:
            for i in next_relations[r]['relation']:
                relations_list.append(r + '->' + i)
        next_relations = relations_list

    return next_relations



def filter_entities(start_entities, sparql_output):
    entities = {start_entities[start_entity]: {} for start_entity in start_entities}
    for i in sparql_output:
        start_entity_id = i['start']['value'].replace("http://rdf.freebase.com/ns/", "")
        start_entity_name = start_entities[start_entity_id]
        if i['e']['type'] == 'uri':
            entity_id = i['e']['value'].replace("http://rdf.freebase.com/ns/", "")
            entity_name = 'NA'
            if 'name' in i:
                entity_name = i['name']['value']
            elif 'wiki' in i:
                entity_name = i['wiki']['value']
            elif 'extra' in i:
                # filter useless extra relations and entities back to start entities
                r = i['r']['value'].replace("http://rdf.freebase.com/ns/", "")
                if r.endswith(('id', 'has_no_value', 'has_value')):
                    continue
                if 'e1' in i:
                    if i['e1']['value'].replace("http://rdf.freebase.com/ns/", "") in start_entities:
                        continue
                if entity_id in entities[start_entity_name]:
                    entity_name = entities[start_entity_name][entity_id] + ', '
                else:
                    entity_name = ''
                content = "{}: {}".format(r.split('.')[-1], i['extra']['value'])
                if content not in entity_name:
                    entity_name += content


        elif i['e']['type'] in ['literal', 'typed-literal']: # text entities (has no id, no head relations)
            entity_id = i['e']['type']
            entity_name = i['e']['value']
    
        entities[start_entity_name].update({entity_id: entity_name})


    return entities


def get_entities(start_entities, relations, topic):
    entities = []
    for relation in relations:
        sparql_output = execute_sparql(sparql_entities % (' '.join(['ns:' + i for i in list(start_entities.keys())]), relation, topic))
        filtered_entities = filter_entities(start_entities, sparql_output)
        for i in filtered_entities:
            filtered_entities[i] = dict(sorted(filtered_entities[i].items(), key=lambda item: item[1]))

        entities.append(filtered_entities)
    
    return entities


def get_entities_distant(paths, relations, topic):
    entities = []
    for relation in relations:
        start_entities = {}
        previous_entities = paths[relation.rsplit('->', 1)[0]]['entities']
        for i in previous_entities:
            for j in previous_entities[i]:
                if j not in ['literal', 'typed-literal']:
                    start_entities.update({j: previous_entities[i][j]})

        sparql_output = execute_sparql(sparql_entities % (' '.join(['ns:' + i for i in list(start_entities.keys())]), relation.rsplit('->', 1)[1], topic))
        filtered_entities = filter_entities(start_entities, sparql_output)
        for i in filtered_entities:
            filtered_entities[i] = dict(sorted(filtered_entities[i].items(), key=lambda item: item[1]))

        entities.append(filtered_entities)
    
    return entities
