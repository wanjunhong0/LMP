import argparse
from utils import prepare_answer, read_jsonl, normalize_str, get_list_str


parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=str,
                    default="webqsp", help="choose the dataset from {cwq, webqsp, grailqa, simpleqa, webquestions}.")
parser.add_argument("--file_path", type=str, 
                    default="./output/original/lmp_webqsp_llama-3_1hop.jsonl", help="the model output file name.")                 
args = parser.parse_args()


def match(answer: str, result: str) -> bool:
    """ If LLM result matches with the answer. """
    answer = [normalize_str(i) for i in answer]
    for ans in answer:
        if ans in normalize_str(result):  # exact match
            return True

    return False
   
def reverse_match(answer: str, result: str) -> bool:   # e.g question: when ...? answer: 2014 world series, result: 2014
    """ If the answer matches with the LLM result. """
    answer = [normalize_str(i) for i in answer]
    result = [normalize_str(i) for i in get_list_str(result)]
    for res in result:
        if any([res in i for i in answer]):
            return True

    return False


answers = prepare_answer(args.dataset)
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
# print([i for i, v in enumerate(hits) if v == 0])
