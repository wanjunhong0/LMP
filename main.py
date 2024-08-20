from tqdm import tqdm
import argparse
from utils import prepare_dataset, save_2_jsonl, run_llm, construct_facts, get_topics
from freebase import get_relations, get_entities, get_relations_distant, get_entities_distant
from propagation import propagate
import random
from prompt import question_prompt


random.seed(123)

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=str,
                    default="cwq", help="choose the dataset from {cwq, webqsp, grailqa, simpleqa, webquestions}.")
parser.add_argument("--limit", type=int,
                    default=7000, help="the max length of the approximation LLMs input.")               
parser.add_argument("--max_length", type=int,
                    default=1000, help="the max length of LLMs output.")
parser.add_argument("--max_retry", type=int,
                    default=5, help="the maximum amount of retry if failed.")
parser.add_argument("--temperature", type=float,
                    default=0., help="the temperature")
parser.add_argument("--depth", type=int,
                    default=3, help="the depth of propagation.")
parser.add_argument("--width", type=int,
                    default=3, help="the number of relations kept.")
parser.add_argument("--llm", type=str,
                    default="llama-3", help="choose base LLM model from {llama-2, llama-3, gpt-3.5-turbo, gpt-4}.")
parser.add_argument("--openai_api_key", type=str,
                    default="", help="if the LLM is gpt-3.5-turbo or gpt-4, you need add your own openai api key.")
parser.add_argument('--verbose', action='store_true', help="print LLM input and output.")
args = parser.parse_args()

datas, question_string = prepare_dataset(args.dataset)


for data in tqdm(datas):
    question = data[question_string]
    topics = get_topics(data['topic_entity'])
    paths = {topics[topic]: {} for topic in topics}

    for topic in topics:
        topic_name = topics[topic]
        for l in range(1, args.depth+1):
            if l == 1:
                relations = get_relations(question, topic, topic_name, args)
                entities = get_entities({topic: topic_name}, relations, topic)
            else:
                relations = get_relations_distant(question, topic, topic_name, relations, paths[topic_name], args)
                entities = get_entities_distant(paths[topic_name], relations, topic)
            [paths[topic_name].update({r: {"entities": entities[i]}}) for i, r in enumerate(relations)]
            paths = propagate(question, topic_name, relations, paths, args)
        # clean paths
        [paths[topic_name].update({r: paths[topic_name][r]['fact']}) for r in paths[topic_name]]

    facts = construct_facts(paths, topics, args, True)
    prompt = question_prompt.format(facts, question)
    response = run_llm(prompt, args)
        

    output = {"question": question, "result": response, "paths": paths}

    save_2_jsonl("lmp_{}_{}_{}hop.jsonl".format(args.dataset, args.llm, args.depth), output)
