import re
from SPARQLWrapper import SPARQLWrapper, JSON
from prompt import relations_reduced_prompt
from utils import run_llm
import random


SPARQLPATH = "http://10.3.216.75:25815/sparql"  # depend on your own internal address and port, shown in Freebase folder's readme.md
# SPARQLPATH= "http://localhost:8000/sparql"

# pre-defined sparqls
sparql_head_relations = """
PREFIX ns: <http://rdf.freebase.com/ns/>
SELECT DISTINCT ?r
WHERE {
ns:%s ?r ?e .
}
"""
# sparql_tail_relations = """
# PREFIX ns: <http://rdf.freebase.com/ns/>
# SELECT DISTINCT ?r
# WHERE {
# ?e ?r ns:%s .
# }
# """
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
sparlql_entity_name_literal = """
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
sparql_head_entities_extract = """PREFIX ns: <http://rdf.freebase.com/ns/>\nSELECT ?tailEntity\nWHERE {\n?tailEntity ns:%s ns:%s  .\n}"""
sparql_id = """PREFIX ns: <http://rdf.freebase.com/ns/>\nSELECT DISTINCT ?tailEntity\nWHERE {\n  {\n    ?entity ns:type.object.name ?tailEntity .\n    FILTER(?entity = ns:%s)\n  }\n  UNION\n  {\n    ?entity <http://www.w3.org/2002/07/owl#sameAs> ?tailEntity .\n    FILTER(?entity = ns:%s)\n  }\n}"""
    
# def check_end_word(s):
#     words = [" ID", " code", " number", "instance of", "website", "URL", "inception", "image", " rate", " count"]
#     return any(s.endswith(word) for word in words)

# def abandon_rels(relation):
#     if relation == "type.object.type" or relation == "type.object.name" or relation.startswith("common.") or relation.startswith("freebase.") or "sameAs" in relation:
#         return True


def execurte_sparql(sparql_query):
    sparql = SPARQLWrapper(SPARQLPATH)
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return results["results"]["bindings"]


# def replace_relation_prefix(relations):
#     return [relation['relation']['value'].replace("http://rdf.freebase.com/ns/","") for relation in relations]

# def replace_entities_prefix(entities):
#     return [entity['tailEntity']['value'].replace("http://rdf.freebase.com/ns/","") for entity in entities]


def id2entity_name_or_type(entity_id):
    sparql_query = sparql_id % (entity_id, entity_id)
    sparql = SPARQLWrapper(SPARQLPATH)
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    if len(results["results"]["bindings"])==0:
        return "UnName_Entity"
    else:
        return results["results"]["bindings"][0]['tailEntity']['value']


def get_relations(question, topic, topic_name, args, top_n):
    head_relations = execurte_sparql(sparql_head_relations % topic)
    head_relations = filter_relations(head_relations)
    if top_n > 0:
        prompt = relations_reduced_prompt.format(top_n, question, topic_name, head_relations)
        response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
        response_list = re.sub(r'\n[0-99]?(spoilers)?', ' ', response.lower()).split(' ')
        response_list = [i.strip("'[]") for i in response_list if i.count('.') > 1]
        reduced_relations = []
        for relation in head_relations:
            if relation in response_list:
                reduced_relations.append(relation)
        while len(reduced_relations) != top_n:
            print('Reduced relations failed, Retrying.')
            print(response)
            reduced_relations = random.sample(head_relations, top_n)

        head_relations = reduced_relations

    return head_relations
            

def filter_relations(sparql_output):
    relations = []
    for i in sparql_output:
        reltion = i['r']['value']
        if reltion.startswith("http://rdf.freebase.com/ns/"):
            relation = reltion.replace("http://rdf.freebase.com/ns/", "")
            if not (relation.startswith("type.")  or relation.startswith("common.") or relation.startswith("freebase.") or relation.endswith("id")):
                relations.append(relation)

    return relations


def get_entities(topic, relations):
    entities_id, entities_name = [], []
    for relation in relations:
        tail_entities = execurte_sparql(sparql_tail_entities % (topic, relation))
        tail_entities_id, tail_entities_name = filter_entities(tail_entities, topic)
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
    name = execurte_sparql(sparql_entity_name % entity_id)
    if len(name) == 0:
        name = execurte_sparql(sparql_entity_name_wiki % entity_id) # try wiki sameas name
        if len(name) == 0:
            name = execurte_sparql(sparlql_entity_name_literal % entity_id) # try if any literal connect to the entity
            if len(name) == 0:
                name = execurte_sparql(sparql_entity_name_1hop % (entity_id, topic)) # try 1-hop entity name except original topic
    
    if len(name) > 0:
        name = ", ".join([i['name']['value'] for i in name])
    else:
        name = 'NA'

    return name

