
# LMP 

The official repository of the ACL 2025 paper "Digest the Knowledge: Large Language Models empowered Message Passing for Knowledge Graph Question Answering".

## Requirement 

### Python Packages
```
SPARQLWrapper
openai
re
tqdm
```

### Datasets

Datasets used in our experiment can be found in the  ```dataset``` folder, which are originally from the repository of [ToG](https://github.com/IDEA-FinAI/ToG/tree/main/data).


### Setup Knowledge Graph

You need to setup Freebase on your local machine by following the [instruction](https://github.com/IDEA-FinAI/ToG/tree/main/Freebase) and also need to specify the server port of SPARQL in the line 7 of ```freebase.py```.

:warning: Since Freebase is a extreme large KG and our SPARQL query for multi-hop search is complex, we recommend you to modify the default config in the `virtuoso.ini` as followed to avoid potential errors of SPARQLWrapper.

```ini
[Parameters]
NumberOfBuffers            = 5450000    ; depending on system memory free (64GB)
MaxDirtyBuffers            = 4000000    ; depending on system memory free (64GB)
ThreadsPerQuery            = 16     ; depending on CPU cores

[SPARQL]
MaxQueryExecutionTime      = 6000    ; increase to avoid queries timeout
```

### Setup LLM Server for open-source LLM

Your need to setup our own LLM server for open-source LLM like Llama 2 & 3.
You can use [vllm](https://docs.vllm.ai/en/stable/) or any other packages you preferred to setup openai compatible server and specify your LLM server port in the line 53 of `util.py`.

## Run LMP

### Usages

Use the following code to run LMP with open-source LLM in your terminal,

``` bash
python main.py --dataset cwq --depth 3 --width 3 --llm llama-3
```

Use the following code to run LMP with closed-API LLM in your terminal,

``` bash
python main.py --dataset webqsp --depth 1 --width 5 --llm gpt-3.5-turbo --api_key sk-...
```

### Arguments

- `--dataset` : choose the dataset to run.
- `--limit_fact` : the max length of each fact.
- `--limit_llm_in` : the max length of LLMs input.
- `--limit_llm_out` : the max length of LLMs output.
- `--max_retry` : the maximum amount of retry if failed.
- `--temperature` : the temperature of LLMs.
- `--depth` : the depth of message passing. :warning: Since we use its 1-hop neighbors information for unnamed entity, $L-1$ round of language message passing may includes $L$-hop information of the topic entity.
- `--width` : the number of relations sampled.
- `--llm` : the backbone LLM to usd.
- `--api_key` : the api key for closed-API LLM.
- `--verbose` : print LLM input and output.

## Evaluation

Use the following code to conduct evaluation,

``` bash
python eval.py --dataset cwq --file_path output/lmp_cwq_llama-3_3hop.json
```

### Original Results

We have released the original results in our experiments using open-source LLMs in the `output/original` folder. Due to company policy, we are NOT going to release the results using closed-API LLMs. 

### :fire: Performance boost with refined prompts

We have refined our prompts with more clarified instructions, which resulted in a relative big performance boost as listed below. The updated results are in the `output` folder. 

| Llama-3-70B                   | WebQSP |  CWQ | GrailQA | SimpleQuestions | WebQuestions |
|-------------------------------|:------:|:----:|:-------:|:---------------:|:------------:|
| Original results in our paper |  89.6  | 72.5 |   80.6  |       80.0      |     76.6     |
| Updated results               |  91.8  | 75.2 |   86.3  |       82.5      |     78.1     |

## Citation
If you are interested or inspired by our work, please star our repository and cite our work by,
```bibtex

```
