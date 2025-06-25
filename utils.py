import json
from openai import OpenAI, APITimeoutError, APIConnectionError
import time
import re
from tqdm import tqdm


def prepare_dataset(dataset_name: str) -> tuple[list, str]:
    """ Load datasets. """
    if dataset_name == 'cwq':
        with open('./dataset/cwq.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'question'
    elif dataset_name == 'webqsp':
        with open('./dataset/WebQSP.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'RawQuestion'
    elif dataset_name == 'grailqa':
        with open('./dataset/grailqa.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'question'
    elif dataset_name == 'simpleqa':
        with open('./dataset/SimpleQA.json',encoding='utf-8') as f:
            datas = json.load(f)    
        question_string = 'question'
    elif dataset_name == 'webquestions':
        with open('./dataset/WebQuestions.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'question'
    else:
        print("dataset not found, you should pick from {cwq, webqsp, grailqa, simpleqa, webquestions}.")
        exit(-1)

    return datas, question_string


def get_topics(topics: dict) -> dict:
    """ Get the entity ids and names of the topic entities. !!! Avoid topic entity with same names. """
    names = []
    for topic in topics:
        topic_name = topics[topic]
        while topic_name in names:
            topic_name = topic_name + ' '
        names.append(topic_name)
        topics.update({topic: topic_name})
    
    return topics


def run_llm(prompt: str, args, history: list = None, retry_prompt: str = None) -> str:
    """ Send prompts into LLM and get response. """
    if "llama" in args.llm.lower():
        base_url = "http://10.3.217.80:29890/v1"  # your local llama server port
        # base_url = "http://localhost:8000/v1"
        client = OpenAI(api_key="EMPTY", base_url=base_url)
        engine = client.models.list().data[0].id
    else:
        client = OpenAI(api_key=args.api_key)
        engine = args.llm
    temperature = args.temperature
    max_tokens = args.limit_llm_out  
    messages = [{"role": "system", "content": "You are an AI assistant that helps people find information."}]
    messages.append({"role": "user", "content": prompt})
    # retry mechanism
    if history is not None:
        temperature = min(1, args.temperature + 0.2 * len(history))
        max_tokens = args.limit_llm_out * 2     # transformer usually failed when output is truncated
        if token_count(prompt + retry_prompt + history[-1]) < args.limit_llm_in:
            messages.append({"role": "assistant", "content": history[-1]})   # only use the last conversation to save token usage
        messages.append({"role": "user", "content": retry_prompt})
    try:
        response = client.chat.completions.create(model=engine, messages=messages, temperature=temperature,
            max_tokens=max_tokens, frequency_penalty=0, presence_penalty=0)
    except APITimeoutError or APIConnectionError:
        time.sleep(10)
        response = client.chat.completions.create(model=engine, messages=messages, temperature=temperature,
            max_tokens=max_tokens, frequency_penalty=0, presence_penalty=0)
               
    result = response.choices[0].message.content

    if args.verbose:
        print('===================input=======================')
        print(prompt)
        print('===================output======================')
        print(result)
        print('===============================================')

    return result
    
def save_2_jsonl(file_name: str, output: dict):
    """ Save results to json file. """
    with open(file_name, "a") as outfile:
        json_str = json.dumps(output)
        outfile.write(json_str + "\n")

def read_jsonl(file_name: str) -> dict:
    """ Read json file. """
    with open(file_name, encoding='utf-8') as f:
        outfile = [json.loads(line) for line in f]

    return outfile

def prepare_answer(dataset_name: str) -> dict:
    """ Load datasets answers for evaluation. """
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

def get_list_str(string: str) -> list:
    """ Retrieve items in numbered lists from the output of LLM. """
    string = '\n' + string      # avoid text start with numbered list, so that the first one can't be matched
    matches = re.findall(r'\n\d+\.\s+(.*?)(?=\n\d+\.|$)', string, re.DOTALL)
    str_list = [match.strip() for match in matches]
    if len(str_list) > 0:
        str_list = [i[i.find(" ")+1:] for i in string.replace('\n\t', ' ').split('\n') if re.match("^\*|\-|[0-99]", i)]
    if len(str_list) > 0:
        str_list[-1] = str_list[-1].split('\n\n')[0]
    
    return str_list

def sort_with_indices(lst: list) -> tuple[list, list]:
    """ Get the sorted list and the indices that would sort the list. """
    sorted_lst = sorted(lst)
    sorted_indices = sorted(range(len(lst)), key=lambda x: lst[x])
    
    return sorted_lst, sorted_indices

def token_count(text: str) -> float:
    """ Approximately count token usage. """
    punctuation = set('!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~')
    number = set('0123456789')

    n_tokens = len("".join(i for i in text if i in punctuation)) 
    text = "".join(i for i in text if i not in punctuation)

    n_tokens += len("".join(i for i in text if i in number)) / 2
    text  = "".join(i for i in text if i not in number)

    n_tokens += len(text) / 4

    return n_tokens

def readout(graphs: dict, topics: dict, args, description: bool = False):
    """ Construct summary outlines from fact graphs. """
    facts = '\n'
    for topic in topics:
        topic_name = topics[topic]
        facts += 'Here are some facts about topic {} that may related to the question.'.format(topic_name)
        relations_1hop = [i for i in list(graphs[topic_name].keys()) if i.count('->') == 0]
        relations_2hop = [i for i in list(graphs[topic_name].keys()) if i.count('->') == 1]
        relations_3hop = [i for i in list(graphs[topic_name].keys()) if i.count('->') == 2]
        i = -1
        for i, r1 in enumerate(relations_1hop):
            facts += '\n{}. {}'.format(i+1, graphs[topic_name][r1])
            j = 1
            for r2 in relations_2hop:
                if r1 in r2:
                    facts += '\n\t{}.{}. {}'.format(i+1, j, graphs[topic_name][r2])
                    k = 1
                    for r3 in relations_3hop:
                        if r2 in r3:
                            facts += '\n\t\t{}.{}.{}. {}'.format(i+1, j, k, graphs[topic_name][r3])
                            k += 1
                    j += 1
            facts += '\n'
        if description:
            from freebase import sparql_entity_description, execute_sparql
            description = execute_sparql(sparql_entity_description % topic)
            if len(description) > 0:
                facts += '\n{}. {}\n'.format(i+2, description[0]['des']['value'])
        facts += '\n'
    
    while token_count(facts) > args.limit_llm_in:
        facts = facts.rsplit('\n', 1)[0]
        
    return facts
