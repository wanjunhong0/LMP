import json
from openai import OpenAI
import time


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
    f = 0
    while(f == 0):
        try:
            response = client.chat.completions.create(
                    model=engine,
                    messages = messages,
                    temperature=temperature,
                    # max_tokens=max_tokens,
                    frequency_penalty=0,
                    presence_penalty=0)
            result = response.choices[0].message.content
            f = 1
        except:
            print("openai error, retry")
            time.sleep(2)
    return result

def save_2_jsonl(file_name, output):
    with open(file_name, "a") as outfile:
        json_str = json.dumps(output)
        outfile.write(json_str + "\n")