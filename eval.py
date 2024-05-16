from tqdm import tqdm
import argparse
from utils import prepare_answer, read_jsonl, normalize_str, get_list_str


parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=str,
                    default="webqsp", help="choose the dataset from {webqsp, cwq}.")
parser.add_argument("--file_path", type=str, 
                    default="./output/lmp_webqsp_llama.jsonl", help="the model output file name.")
parser.add_argument("--alias", action='store_true', help="consider answer alias.")                  
args = parser.parse_args()

def match(answer, result):
    answer = [normalize_str(i) for i in answer]
    result = normalize_str(result)
    for ans in answer:
        if ans in result or all([i in result for i in ans.split(' ')]):
            return True
    return False
   
def reverse_match(answer, result):
    answer = [normalize_str(i) for i in answer]
    result = [normalize_str(i) for i in get_list_str(result)]
    for res in result:
        if any([res in i for i in answer]):
            return True
    return False


answers = prepare_answer(args.dataset, alias=args.alias)
results = read_jsonl(args.file_path)
hits = []

for result in results:
    answer = answers[result['question']]
    result = result['result']
    if match(answer, result) or reverse_match(answer, result):
        hits.append(1)
    else:
        hits.append(0)

print("# of Correct: {}".format(sum(hits)))
print("# of Wrong: {}".format(len(hits)- sum(hits)))
print("Hit@1: {}".format(sum(hits) / len(hits)))