import re
from SPARQLWrapper import SPARQLWrapper, JSON
from prompt import relations_reduced_prompt
from utils import run_llm
import random


SPARQLPATH = "http://10.3.216.75:25815/sparql"  # depend on your own internal address and port, shown in Freebase folder's readme.md
# SPARQLPATH= "http://localhost:8890/sparql"

# pre-defined sparql
sparql_head_relations = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
ns:%s ?r ?e .
}
"""
sparql_tail_relations = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
?e ?r ns:%s .
}
"""
sparql_tail_entities = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?e
WHERE {
ns:%s ns:%s ?e .
}
""" 
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


def get_relations(question, topic, topic_name, args, top_n):
    head_relations = execute_sparql(sparql_head_relations % topic)
    head_relations = filter_relations(head_relations)
    if len(head_relations) > top_n > 0:
        prompt = relations_reduced_prompt.format(top_n, question, topic_name, '; '.join(head_relations))
        response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
        reduced_relations = get_reduced_relations(response, head_relations)
        while len(reduced_relations) < (top_n - 2):
            print('Reduced relations failed, Retrying.')
            print(response)
            response = run_llm(prompt, 1, args.max_length, args.openai_api_key, args.llm)
            reduced_relations = get_reduced_relations(response, head_relations)

        head_relations = reduced_relations

    return head_relations
            

def filter_relations(sparql_output):
    relations = []
    for i in sparql_output:
        relation = i['r']['value']
        if relation.startswith("http://rdf.freebase.com/ns/"):
            relation = relation.replace("http://rdf.freebase.com/ns/", "")
            if not (relation.startswith(('kg', 'imdb', 'common', 'type', 'freebase')) or relation.endswith(('id', 'msrp', 'number', 'amount', 'permission', 'email', 'unemployment_rate', 'population')) or 'gdp' in relation):
                relations.append(relation)

    return relations


def get_reduced_relations(response, relations):
    response_list = re.sub(r'\n[0-99]?(\*)?(\-)?', ' ', response.lower()).split(' ')
    response_list = [i.strip("'[]") for i in response_list if i.count('.') > 1]
    reduced_relations = []
    for relation in relations:
        if relation in response_list:
            reduced_relations.append(relation)

    return reduced_relations

def get_entities(topic, relations):
    entities_id, entities_name = [], []
    for relation in relations:
        tail_entities = execute_sparql(sparql_tail_entities % (topic, relation))
        ### !!! some relations like m.04n32 --> music.artist.track has 8477 tail entities
        tail_entities_id, tail_entities_name = filter_entities(tail_entities[:50], topic)
        entities_id.append(tail_entities_id)
        entities_name.append(tail_entities_name)
    return entities_id, entities_name


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

