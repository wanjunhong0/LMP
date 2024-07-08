import json
from openai import OpenAI
import time
import re
from tqdm import tqdm
from colorama import Fore, init


init(autoreset=True)
def timer_func(func):
    # This function shows the execution time of the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time.time()
        result = func(*args, **kwargs)
        t2 = time.time()
        print(Fore.RED + f'Function {func.__name__!r} executed in {(t2-t1):.4f}s')
        return result
    return wrap_func

def prepare_dataset(dataset_name):
    if dataset_name == 'cwq':
        with open('./data/cwq.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'question'
    elif dataset_name == 'webqsp':
        with open('./data/WebQSP.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'RawQuestion'
    elif dataset_name == 'grailqa':
        with open('./data/grailqa.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'question'
    elif dataset_name == 'simpleqa':
        with open('./data/SimpleQA.json',encoding='utf-8') as f:
            datas = json.load(f)    
        question_string = 'question'
    elif dataset_name == 'webquestions':
        with open('./data/WebQuestions.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'question'
    else:
        print("dataset not found, you should pick from {cwq, webqsp, grailqa, simpleqa, webquestions}.")
        exit(-1)
    return datas, question_string



def run_llm(prompt, args, history=None, retry_prompt=None):
    if "llama" in args.llm.lower():
        openai_api_base = "http://10.3.216.75:38842/v1"  # your local llama server port
        # openai.api_base = "http://localhost:8000/v1"
        client = OpenAI(api_key="EMPTY", base_url=openai_api_base)
        engine = client.models.list().data[0].id
    else:
        client = OpenAI(api_key=args.openai_api_key)
        engine = args.llm
    temperature = args.temperature  
    messages = [{"role": "system", "content": "You are an AI assistant that helps people find information."}]
    messages.append({"role": "user", "content": prompt})
    if history is not None:
        temperature = min(1, args.temperature + 0.1 * len(history))
        # for i in history[-1:]:
            # while token_count(str(messages)) < args.limit:
        messages.append({"role": "assistant", "content": history[-1]})
        messages.append({"role": "user", "content": retry_prompt})
    response = client.chat.completions.create(model=engine, messages=messages, temperature=temperature,
            # max_tokens=args.max_length,
            frequency_penalty=0, presence_penalty=0)
    result = response.choices[0].message.content

    if args.verbose:
        print('===================input======================')
        print(prompt)
        print('===================output======================')
        print(result)

    return result
    
def save_2_jsonl(file_name, output):
    with open(file_name, "a") as outfile:
        json_str = json.dumps(output)
        outfile.write(json_str + "\n")

def read_jsonl(file_name):
    with open(file_name, encoding='utf-8') as f:
        outfile = [json.loads(line) for line in f]
    return outfile

def prepare_answer(dataset_name, alias=False):
    datas, question_string = prepare_dataset(dataset_name)
    answer_dict = {}
    if dataset_name == 'webqsp':
        for data in tqdm(datas):
            answer_list = []
            for i in data['Parses']:
                for answer in i['Answers']:
                    if answer['EntityName'] == None:
                        answer_list.append(answer['AnswerArgument'])
                    else:
                        answer_list.append(answer['EntityName'])
                        if alias:
                            from freebase import sparql_entity_alias, execute_sparql
                            answer_alias = execute_sparql(sparql_entity_alias % answer['AnswerArgument'])
                            if len(answer_alias) > 0:
                                answer_alias = [i['alias']['value'] for i in answer_alias]
                                answer_list += answer_alias
            answer_dict.update({data[question_string]: list(set(answer_list))})
    elif dataset_name == 'cwq':
        for data in tqdm(datas):
            answer_dict.update({data[question_string]: [data['answer']]})
    elif dataset_name == 'grailqa':
        for data in tqdm(datas):
            answer_list = []
            for answer in data['answer']:
                if "entity_name" in answer:
                    answer_list.append(answer['entity_name'])
                else:
                    answer_list.append(answer['answer_argument'])
            answer_dict.update({data[question_string]: list(set(answer_list))})
    elif dataset_name == 'simpleqa':
        for data in tqdm(datas):
            answer_dict.update({data[question_string]: [data['answer']]})
    elif dataset_name == 'webquestions':
        for data in tqdm(datas):
            answer_dict.update({data[question_string]: data['answers']})

    return answer_dict

def normalize_str(string):
    """Lower text and remove punctuation, articles and extra whitespace."""
    string = string.lower()
    exclude = set('!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~')
    string = "".join(char for char in string if char not in exclude)
    string = re.sub(r"\b(a|an|the|of)\b", " ", string)
    string = " ".join(string.split())
    return string

def get_list_str(string):
    string = '\n' + string      # avoid text start with numbered list, so that the first one can't be matched
    matches = re.findall(r'\n\d+\.\s+(.*?)(?=\n\d+\.|$)', string, re.DOTALL)
    str_list = [match.strip() for match in matches]

    # str_list = [i[i.find(" ")+1:] for i in string.replace('\n\t', ' ').split('\n') if re.match("^\*|\-|[0-99]", i)]

    return str_list

def token_count(text):
    punctuation = set('!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~')
    number = set('0123456789')

    n_tokens = len("".join(i for i in text if i in punctuation))
    text = "".join(i for i in text if i not in punctuation)

    n_tokens += len("".join(i for i in text if i in number)) /2
    text  = "".join(i for i in text if i not in number)

    n_tokens += len(text) / 4

    return n_tokens

def construct_facts(paths, topics, description=False):
    facts = ''
    for topic in topics:
        topic_name = topics[topic]
        facts += 'Here are some facts about topic {} that may related to the question.'.format(topic_name)
        relations_1hop = [i for i in list(paths[topic_name].keys()) if i.count('->') == 0]
        relations_2hop = [i for i in list(paths[topic_name].keys()) if i.count('->') == 1]
        relations_3hop = [i for i in list(paths[topic_name].keys()) if i.count('->') == 2]
        i = -1
        for i, r1 in enumerate(relations_1hop):
            facts += '\n{}. {}'.format(i+1, paths[topic_name][r1])
            j = 1
            for r2 in relations_2hop:
                if r1 in r2:
                    facts += '\n\t{}.{}. {}'.format(i+1, j, paths[topic_name][r2])
                    k = 1
                    for r3 in relations_3hop:
                        if r2 in r3:
                            facts += '\n\t\t{}.{}.{}. {}'.format(i+1, j, k, paths[topic_name][r3])
                            k += 1
                    j += 1
            facts += '\n'
        if description:
            from freebase import sparql_entity_description, execute_sparql
            description = execute_sparql(sparql_entity_description % topic)
            if len(description) > 0:
                facts += '\n{}. {}\n'.format(i+2, description[0]['des']['value'])
        facts += '\n'

    return facts
