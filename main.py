from tqdm import tqdm
import argparse
from utils import prepare_dataset, save_2_jsonl, run_llm, construct_facts
from freebase import get_relations, get_entities, get_relations_distant, get_entities_distant
from propagation import propagate
import random
from prompt import question_prompt


random.seed(123)

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=str,
                    default="simpleqa", help="choose the dataset from {cwq, webqsp, grailqa, simpleqa, webquestions}.")
parser.add_argument("--limit", type=int,
                    default=7000, help="the max length of the approximation LLMs input.")               
parser.add_argument("--max_length", type=int,
                    default=1024, help="the max length of LLMs output.")
parser.add_argument("--temperature", type=float,
                    default=0., help="the temperature")
parser.add_argument("--llm", type=str,
                    default="llama-3", help="choose base LLM model from {llama-2, llama-3, gpt-3.5-turbo, gpt-4}.")
parser.add_argument("--openai_api_key", type=str,
                    default="", help="if the LLM is gpt-3.5-turbo or gpt-4, you need add your own openai api key.")
parser.add_argument('--verbose', action='store_true', help="print LLM input and output.")
args = parser.parse_args()

datas, question_string = prepare_dataset(args.dataset)

# datas = datas[2943:]

for data in tqdm(datas):
    question = data[question_string]
    topics = data['topic_entity']
    paths = {topics[topic]: {} for topic in topics}

    for topic in topics:
        topic_name = topics[topic]
        # 1-hop propagation
        relations = get_relations(question, topic, topic_name, args, 3)
        entities = get_entities({topic: topic_name}, relations, topic)
        [paths[topic_name].update({r: {"entities": entities[i]}}) for i, r in enumerate(relations)]
        facts = propagate(question, topic_name, relations, paths[topic_name], 1, args)
        [paths[topic_name][r].update({"fact": facts[i]}) for i, r in enumerate(relations)]
        # 2-hop propagation
        relations = get_relations_distant(question, topic, topic_name, relations, paths[topic_name], args, 3)
        entities = get_entities_distant(paths[topic_name], relations, topic)
        [paths[topic_name].update({r: {"entities": entities[i]}}) for i, r in enumerate(relations)]
        facts = propagate(question, topic_name, relations, paths[topic_name], 2, args)
        [paths[topic_name][r].update({"fact": facts[i]}) for i, r in enumerate(relations)]
        # 3-hop propagation
        relations = get_relations_distant(question, topic, topic_name, relations, paths[topic_name], args, 3)
        entities = get_entities_distant(paths[topic_name], relations, topic)
        [paths[topic_name].update({r: {"entities": entities[i]}}) for i, r in enumerate(relations)]
        facts = propagate(question, topic_name, relations, paths[topic_name], 3, args)
        [paths[topic_name][r].update({"fact": facts[i]}) for i, r in enumerate(relations)]
        # # # clean paths
        [paths[topic_name].update({r: paths[topic_name][r]['fact']}) for r in paths[topic_name]]

    facts = construct_facts(paths, topics, True)
    prompt = question_prompt.format(facts, question)
    response = run_llm(prompt, args)
    output = {"question": question, "result": response, "paths": paths}

    save_2_jsonl("lmp_{}_{}_1hop.jsonl".format(args.dataset, args.llm), output)
