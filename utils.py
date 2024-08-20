import json
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
import time
import re
from tqdm import tqdm
from colorama import Fore, init


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


def get_topics(topics):
    names = []
    for topic in topics:
        topic_name = topics[topic]
        while topic_name in names:
            topic_name = topic_name + ' '
        names.append(topic_name)
        topics.update({topic: topic_name})
    return topics


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
        temperature = min(1, args.temperature + 0.2 * len(history))
        messages.append({"role": "assistant", "content": history[-1]})
        messages.append({"role": "user", "content": retry_prompt})
    try:
        response = client.chat.completions.create(model=engine, messages=messages, temperature=temperature,
            max_tokens=args.max_length,
            frequency_penalty=0, presence_penalty=0)
    except RateLimitError:
        time.sleep(60)
        response = client.chat.completions.create(model=engine, messages=messages, temperature=temperature,
            max_tokens=args.max_length,
            frequency_penalty=0, presence_penalty=0)
    except APITimeoutError:
        time.sleep(10)
        response = client.chat.completions.create(model=engine, messages=messages, temperature=temperature,
            max_tokens=args.max_length,
            frequency_penalty=0, presence_penalty=0)
    except APIConnectionError:
        time.sleep(10)
        response = client.chat.completions.create(model=engine, messages=messages, temperature=temperature,
            max_tokens=args.max_length,
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
    if len(str_list) > 0:
        str_list = [i[i.find(" ")+1:] for i in string.replace('\n\t', ' ').split('\n') if re.match("^\*|\-|[0-99]", i)]
    if len(str_list) > 0:
        str_list[-1] = str_list[-1].split('\n\n')[0]
    return str_list

def sort_with_indices(lst):
    # Get the sorted list and the indices that would sort the list
    sorted_lst = sorted(lst)
    sorted_indices = sorted(range(len(lst)), key=lambda x: lst[x])
    
    return sorted_lst, sorted_indices

def token_count(text):
    punctuation = set('!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~')
    number = set('0123456789')

    n_tokens = len("".join(i for i in text if i in punctuation))
    text = "".join(i for i in text if i not in punctuation)

    # n_tokens += len("".join(i for i in text if i in number)) / 1    # for Llama-2
    n_tokens += len("".join(i for i in text if i in number)) / 2
    text  = "".join(i for i in text if i not in number)

    n_tokens += len(text) / 4

    return n_tokens

def construct_facts(paths, topics, args, description=False):
    facts = '\n'
    for topic in topics:
        topic_name = topics[topic]
        facts += 'Here are some facts about topic {} that may related to the question.'.format(topic_name)
        relations_1hop = [i for i in list(paths[topic_name].keys()) if i.count('->') == 0]
        relations_2hop = [i for i in list(paths[topic_name].keys()) if i.count('->') == 1]
        relations_3hop = [i for i in list(paths[topic_name].keys()) if i.count('->') == 2]
        i = -1
        for i, r1 in enumerate(relations_1hop):
            facts += '\n{}. {}'.format(i+1, paths[topic_name][r1][:args.max_length])
            j = 1
            for r2 in relations_2hop:
                if r1 in r2:
                    facts += '\n\t{}.{}. {}'.format(i+1, j, paths[topic_name][r2][:args.max_length])
                    k = 1
                    for r3 in relations_3hop:
                        if r2 in r3:
                            facts += '\n\t\t{}.{}.{}. {}'.format(i+1, j, k, paths[topic_name][r3][:args.max_length])
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
