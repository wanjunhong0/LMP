
# LMP Language Model empowered Propagation

The code of Paper: 'Digest the Knowledge: Large Language Model empowered Message Passing on Knowledge Graph'

## Requirement Package

```python
Python 3.8.5 
SPARQLWrapper 2.0.0 
openai 1.34.0
```

## Datasets

Datasets used in our experiment can be found at ```dataset``` folder, which are from the repository of [ToG](https://github.com/IDEA-FinAI/ToG/tree/main/data).

## Run LMP

### Knowledge Setup

Before running, you need to setup Freebase on your local machine by following the [instruction](https://github.com/IDEA-FinAI/ToG/tree/main/Freebase) and you need to specify the server port of SPARQL in ```freebase.py``` also.

### LLM Setup

You can directly use openai API. For Llama-2 and Llama-3, you can use any openai compatible server like [vllm](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html) that we used.

### Example usage

Take cwq dataset as an instance, use the following code to run LMP,

``` python
python main.py --dataset cwq --temperature 0 --depth 3 --width 3 --llm llama-3
```

* `--dataset`: choose the dataset to run
* `-- limit`: the max length of LLMs output
* `--max_retry`: the maximum amount of retry if failed
* `--temperature`: the temperature of LLMs
* `--depth`: the depth of propagation
* `--width`: the number of relations kept
* `--llm`: backbone LLM
* `--openai_api_key`: api key of openai
* `--verbose`: print LLM input and output

 Note that if you want to use ChatGPT or GPT4, you need to add your own openai key.

 If you want to use Llama-2 or Llama-3, add your server port in line 50 in ```utils.py```.

## Evaluation

Take cwq dataset as an instance, use the following code to conduct evaluation,

``` python
python eval.py --dataset cwq --file_path output/lmp_cwq_llama-3_3hop.json
```
