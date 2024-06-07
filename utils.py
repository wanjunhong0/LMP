import json
from openai import OpenAI
import time
import re
from tqdm import tqdm


def prepare_dataset(dataset_name):
    if dataset_name == 'cwq':
        with open('./data/cwq.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'question'
    elif dataset_name == 'webqsp':
        with open('./data/WebQSP.json',encoding='utf-8') as f:
            datas = json.load(f)
        question_string = 'RawQuestion'
    else:
        print("dataset not found, you should pick from {cwq, webqsp}.")
        exit(-1)
    return datas, question_string

def run_llm(prompt, temperature, max_tokens, openai_api_keys, engine="gpt-3.5-turbo"):
    if "llama" in engine.lower():
        openai_api_key = "EMPTY"
        openai_api_base = "http://10.3.216.75:20686/v1"  # your local llama server port
        # openai.api_base = "http://localhost:8000/v1"
        client = OpenAI(api_key=openai_api_key, base_url=openai_api_base)
        engine = client.models.list().data[0].id
    else:
        client = OpenAI(api_key=openai_api_keys)
        
    messages = [{"role": "system", "content": "You are an AI assistant that helps people find information."}]
    message_prompt = {"role": "user", "content": prompt}
    messages.append(message_prompt)
    response = client.chat.completions.create(
            model=engine,
            messages = messages,
            temperature=temperature,
            # max_tokens=max_tokens,
            frequency_penalty=0,
            presence_penalty=0)
    result = response.choices[0].message.content

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
    str_list = [i[i.find(" ")+1:] for i in string.replace('\n\t', ' ').split('\n') if re.match("^\*|\-|[0-99]", i)]

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

