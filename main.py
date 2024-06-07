from tqdm import tqdm
import argparse
from utils import prepare_dataset, save_2_jsonl, run_llm
from freebase import get_relations, get_entities, get_relations_2hop, get_entities_2hop
from propagation import propagate, get_propagate_list
import random
from prompt import question_prompt


random.seed(123)

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=str,
                    default="cwq", help="choose the dataset from {webqsp, cwq}.")
parser.add_argument("--max_length", type=int,
                    default=1024, help="the max length of LLMs output.")
parser.add_argument("--temperature", type=float,
                    default=0., help="the temperature")
parser.add_argument("--llm", type=str,
                    default="llama-3", help="choose base LLM model from {llama, gpt-3.5-turbo, gpt-4}.")
parser.add_argument("--openai_api_key", type=str,
                    default="", help="if the LLM is gpt-3.5-turbo or gpt-4, you need add your own openai api key.")
args = parser.parse_args()


datas, question_string = prepare_dataset(args.dataset)

datas = datas[12:]

for data in tqdm(datas):
    question = data[question_string]
    topics = data['topic_entity']
    paths = {topics[topic]: {} for topic in topics}

    for topic in topics:
        topic_name = topics[topic]
        relations = get_relations(question, topic, topic_name, args, 5)
        entities_id, entities_name = get_entities(topic, relations)
        [paths[topic_name].update({r: {"entities_id": entities_id[i], "entities_name": entities_name[i]}}) for i, r in enumerate(relations)]

        facts = propagate(question, topic_name, paths[topic_name], args)
        [paths[topic_name][r].update({"fact": facts[i]}) for i, r in enumerate(relations)]

    for topic in topics:
        topic_name = topics[topic]
        relations = get_relations_2hop(question, topic, topic_name, paths[topic_name], args, 3)
        entities_id, entities_name = get_entities_2hop(topic, relations)
        [paths[topic_name].update({r: {"entities_id": entities_id[i], "entities_name": entities_name[i]}}) for i, r in enumerate(relations)]

        facts = propagate(question, propagate_list, args)
        [paths[topic_name][r].update({"fact": facts[i]}) for i, r in enumerate(relations)]

    facts = []
    for i in paths:
        for j in paths[i]:
            fact = paths[i][j]['fact']
            facts.append(fact)
            paths[i].update({j: fact})
    prompt = question_prompt.format("\n".join(facts), question)
    response = run_llm(prompt, args.temperature, args.max_length, args.openai_api_key, args.llm)
    output = {"question": question, "result": response, "paths": paths}

    save_2_jsonl("lmp_{}_{}_2hop_direct_1.jsonl".format(args.dataset, args.llm), output)
