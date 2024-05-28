from tqdm import tqdm
import argparse
from utils import prepare_dataset, save_2_jsonl, run_llm
from freebase import get_relations, get_entities
from propagation import propagate, get_propagate_list
import random
from prompt import question_prompt


random.seed(123)

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=str,
                    default="webqsp", help="choose the dataset from {webqsp, cwq}.")
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

# datas = datas[1584:]

for data in tqdm(datas):
    question = data[question_string]
    topics = data['topic_entity']
    paths = {}
    for topic in topics:
        topic_name = topics[topic]
        relations = get_relations(question, topic, topic_name, args, 5)
        paths.update({topic_name: relations})

    output = {question: paths}
    save_2_jsonl("relations_{}_{}.jsonl".format(args.dataset, args.llm), output)