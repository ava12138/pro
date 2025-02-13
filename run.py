import os
import json
import yaml
import argparse
import time
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer
from openai import OpenAI
from PromptFramwork import PromptFramework as pf
from utils.utils import initialize_seeds
from utils.utils import format_question_output, format_rationale_output, format_distractor_output


# 定义函数来逐条读取测试集
def read_test_data_iter(test_file):
    with open(test_file, 'r') as f:
        test_data = json.load(f)
        for item in test_data:
            yield {
                "question": item["question"],
                "correct_answer": item["correct_answer"],
                "support": item["support"]
            }

# 定义函数来追加写入结果文件
def append_to_output_file(output_file, data):
    if os.path.exists(output_file):
        with open(output_file, 'r+') as f:
            try:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
            except json.JSONDecodeError:
                existing_data = []
            existing_data.append(data)
            f.seek(0)
            json.dump(existing_data, f, indent=4)
    else:
        with open(output_file, 'w') as f:
            json.dump([data], f, indent=4)

# 加载配置
def load_config():
    with open('./config/api.yaml', 'r') as file:
        api_config = yaml.safe_load(file)
    with open('./config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    with open('./config/principle.json', 'r') as file:
        principles_config = json.load(file)
    return api_config, config, principles_config


# 初始化本地模型
def initialize_local_model(model_name_or_path, gpu_id):
    # 通过指定 GPU 设备加载模型
    device = torch.device(f"cuda:{gpu_id}" if torch.cuda.is_available() else "cpu")
    model = AutoModelForCausalLM.from_pretrained(model_name_or_path).to(device)
    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
    return model, tokenizer, device

# 直接调用本地模型进行推理
def get_local_response(model, tokenizer, prompt, device, temperature=1.0, top_p=1.0, presence_penalty=0.0):
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    # 设置生成的参数
    output = model.generate(
        **inputs,
        max_length=512,
        temperature=temperature,
        top_p=top_p,
        presence_penalty=presence_penalty,
        num_return_sequences=1,
    )
    
    response = tokenizer.decode(output[0], skip_special_tokens=True)
    return response

def process_test_data(model, tokenizer, test_file, output_file, prompt_config, distractor_principle, temperature, top_p, presence_penalty, device):
    total_items = sum(1 for _ in read_test_data_iter(test_file))
    start_time = time.time()
    # 初始化token计数

    with tqdm(total=total_items, desc="Generating distractors") as pbar:
        for question_data in read_test_data_iter(test_file):
            try:
                rg_prompt = pf.producePrompt(prompt_config['rg'], question_data, distractor_principle)
                r = get_local_response(model, tokenizer, rg_prompt, device, temperature, top_p, presence_penalty)
                # print("错误推理:\n", r)

                inference = format_rationale_output(r, prompt_config['format'])
                dg_prompt = pf.producePrompt(prompt_config['dg'], question_data)
                # print("观察dg的prompt:\n", dg_prompt)
                d = get_local_response(model, tokenizer, dg_prompt, device, temperature, top_p, presence_penalty)


                extracted_distractors = format_distractor_output(d)
                print("提取的干扰项:", extracted_distractors)
                result = {
                    "question": question_data['question'],
                    "correct_answer": question_data['correct_answer'],
                    "distractor1": extracted_distractors['distractor1'],
                    "distractor2": extracted_distractors['distractor2'],
                    "distractor3": extracted_distractors['distractor3']
                }
                append_to_output_file(output_file, result)
            finally:
                pbar.update(1)
                elapsed = time.time() - start_time

    print(f"\nGeneration completed:")
    print(f"Total time: {time.time() - start_time:.2f}s")
    print(f"Results saved to {output_file}")


def main():

    # 解析参数
    parser = argparse.ArgumentParser(description="Generate distractors")
    parser.add_argument('-d', '--dataset', choices=['lan', 'nat', 'soc', 'sciqa-text', 'sciq'], required=True, help="Type of test file to process")
    parser.add_argument('-m', '--model', choices=['plus', 'qwen7b'], required=True, help="Type of model to use")
    parser.add_argument('-p', '--prompt', choices=['rule', 'cot', 'non'], required=True, help="Prompt type")
    parser.add_argument('-s', '--seed', type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument('-g', '--gpu', type=int, default=0, help="GPU ID to use")  
    args = parser.parse_args()

    # 加载配置
    api_config, config, principles_config = load_config()
    distractor_principle = principles_config['distractor_principle']
    prompt_config = config['prompt_types'][args.prompt]
    file_config = config['files'][args.dataset]

    initialize_seeds(args.seed)
    # 初始化本地模型
    model_name_or_path = "path_to_your_local_model"  # 本地模型的路径
    model, tokenizer, device = initialize_local_model(model_name_or_path, args.gpu)


    # 配置文件路径
    test_file = file_config['test_file']
    output_file = f"{file_config['output_file']}-{args.model}-{args.prompt}.json"

    # 参数配置
    temperature = config['temperature']
    top_p = config['top_p']
    presence_penalty = config['presence_penalty']

    # 处理测试数据
    process_test_data(model, tokenizer, test_file, output_file, prompt_config, distractor_principle, temperature, top_p, presence_penalty, device)

if __name__ == "__main__":
    main()





# # 示例用法
# test_filename = "./data_divided/sciqa-test-lan.json"
# output_filename = "./output/output_dg-sciqa-lan.json"

# # 逐条读取和处理测试集
# for question_data in read_test_data_iter(test_filename):
#     # qg_prompt = pf.producePrompt("qg", examples=question_examples)
#     # q = get_response(qg_prompt)
#     # print("出的题:\n", q)
#     # questiondata = format_question_output(q)
#     # print("题目信息:", questiondata)
    
#     rg_prompt = pf.producePrompt("rg", question_data, distractor_principle)
#     r = get_response(rg_prompt)
#     print("错误推理:\n", r)

#     example = format_rationale_output(r)
#     dg_prompt = pf.producePrompt("dg", question_data, example)
#     print("观察dg的prompt:\n", dg_prompt)
#     d = get_response(dg_prompt)

#     extracted_distractors = format_distractor_output(d)
#     print("提取的干扰项:", extracted_distractors)
#     # 将结果打包为一个JSON对象
#     result = {
#         "question": question_data['question'],
#         "correct_answer": question_data['correct_answer'],
#         "distractor1": extracted_distractors['distractor1'],
#         "distractor2": extracted_distractors['distractor2'],
#         "distractor3": extracted_distractors['distractor3']
#     }
    
#     # 追加写入结果文件
#     append_to_output_file(output_filename, result)

# print(f"所有干扰项已保存到 {output_filename}")


# with open('./config/api.yaml', 'r') as file:
#     api_config = yaml.safe_load(file)
#     api_key = api_config['api_key']
#     api_model = api_config['model']

# with open('./config/config.yaml', 'r') as file:
#     config = yaml.safe_load(file)
#     temperature = config['temperature']
#     top_p = config['top_p']
#     presence_penalty = config['presence_penalty']

# with open('./config/principle.json', 'r') as file:
#     principles_config = json.load(file)
#     distractor_principle = principles_config['distractor_principle']

# client = OpenAI(
#         api_key=api_key, 
#         base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
#     )

# file_path_sciq = os.path.expanduser('/data/lzx/sciq/train.json')
# with open(file_path_sciq, 'r') as file:
#     data = json.load(file)

# question_examples = [data[0], data[1]]

# 定义函数来获取响应
# qg_prompt = pf.producePrompt("qg", examples=question_examples)    
# q = get_response(qg_prompt)
# print("出的题:\n", q)
# questiondata = format_question_output(q)
# print("题目信息:", questiondata)
# rg_prompt = pf.producePrompt("rg", questiondata, distractor_principle)
# # print(dg_prompt)
# r = get_response(rg_prompt)
# print("错误推理:\n", r)

# example = format_rationale_output(r)
# dg_prompt = pf.producePrompt("dg", questiondata, example)
# d = get_response(dg_prompt)
# print("干扰项:\n", d)