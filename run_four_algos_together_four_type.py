import subprocess
import os
import json
import shutil
from pathlib import Path
import pandas as pd

# ================= USER-DEFINED VARIABLES ====================
trace_file = "data/processed_traces/new_traces/fig11_four_type_mmpp2.csv"
df = pd.read_csv(trace_file)
num_requests = len(df)


prompt_types = [
    {"type": "type1", "prefill": 10, "decode": 20, "arrival_rate": 18},
    {"type": "type2", "prefill": 10, "decode": 40, "arrival_rate": 34},
    {"type": "type3", "prefill": 10, "decode": 80, "arrival_rate": 68},
    {"type": "type4", "prefill": 10, "decode": 160, "arrival_rate": 138},
]

prompt_type_flag = json.dumps(prompt_types)
batch_size = 256
booking_limit = 256
results_root = "results_4_tests"
# =============================================================

os.makedirs(results_root, exist_ok=True)

tests = [
    {
        "name": "our_modified_booking_limit",
        "command": [
            "--replica_scheduler_config_type", "our_modified_booking_limit",
            "--our_modified_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
            "--our_modified_booking_limit_scheduler_config_total_num_requests", str(num_requests),
            "--our_modified_booking_limit_scheduler_config_total_limit", str(booking_limit),
            "--our_modified_booking_limit_scheduler_config_force_clear"
        ]
    },
    {
        "name": "modified_booking_limit",
        "command": [
            "--replica_scheduler_config_type", "modified_booking_limit",
            "--modified_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
            "--modified_booking_limit_scheduler_config_total_num_requests", str(num_requests),
            "--modified_booking_limit_scheduler_config_total_limit", str(booking_limit),
            "--modified_booking_limit_scheduler_config_force_clear"
        ]
    },
    # {
    #     "name": "modified_nested_wait",
    #     "command": [
    #         "--replica_scheduler_config_type", "modified_general_nested_booking_limit",
    #         "--modified_general_nested_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
    #         "--modified_general_nested_booking_limit_scheduler_config_total_limit", str(booking_limit),
    #         "--modified_general_nested_booking_limit_scheduler_config_total_num_requests", str(num_requests),
    #         "--modified_general_nested_booking_limit_scheduler_config_force_clear"
    #     ]
    # },
    # {
    #     "name": "nested_wait",
    #     "command": [
    #         "--replica_scheduler_config_type", "general_nested_booking_limit",
    #         "--general_nested_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
    #         "--general_nested_booking_limit_scheduler_config_total_limit", str(booking_limit),
    #         "--general_nested_booking_limit_scheduler_config_total_num_requests", str(num_requests),
    #         "--general_nested_booking_limit_scheduler_config_force_clear"
            
    #     ]
    # },
    {
        "name": "sarathi",
        "command": [
            "--replica_scheduler_config_type", "sarathi",
            "--sarathi_scheduler_config_batch_size_cap", str(batch_size)
        ]
    },
    {
        "name": "vllm",
        "command": [
            "--replica_scheduler_config_type", "vllm",
            "--vllm_scheduler_config_batch_size_cap", str(batch_size)
        ]
    },
    # {   
    #     "name": "arrival_rate_update_nested_wait",
    #     "command": [
    #         "--replica_scheduler_config_type", "arrival_rate_update_general_nested_booking_limit",
    #         "--arrival_rate_update_general_nested_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
    #         "--arrival_rate_update_general_nested_booking_limit_scheduler_config_total_limit", str(booking_limit),
    #         "--arrival_rate_update_general_nested_booking_limit_scheduler_config_total_num_requests", str(num_requests),
    #         "--arrival_rate_update_general_nested_booking_limit_scheduler_config_force_clear"
    #     ]
    # },
]

for test in tests:
    test_name = test["name"]
    result_dir = os.path.join(results_root, test_name)
    os.makedirs(result_dir, exist_ok=True)

    command = [
        "python", "-m", "vidur.main",
        "--replica_config_device", "a100",
        "--replica_config_model_name", "meta-llama/Meta-Llama-3-8B",
        "--cluster_config_num_replicas", "1",
        "--replica_config_tensor_parallel_size", "1",
        "--replica_config_num_pipeline_stages", "1",
        "--request_generator_config_type", "trace_replay",
        "--trace_request_generator_config_trace_file", trace_file,
        "--random_forrest_execution_time_predictor_config_prediction_max_prefill_chunk_size", "16384",
        "--random_forrest_execution_time_predictor_config_prediction_max_batch_size", "2048",
        "--random_forrest_execution_time_predictor_config_prediction_max_tokens_per_request", "16384",
        "--metrics_config_output_dir", result_dir
    ] + test["command"]

    print(f"[Running] {test_name}")
    log_path = os.path.join(result_dir, "output.log")
    with open(log_path, "w") as log_file:
        subprocess.run(command, stdout=log_file, stderr=subprocess.STDOUT)

    # Move contents from timestamp folder if it exists
    inner_dirs = [d for d in Path(result_dir).iterdir() if d.is_dir() and d.name.startswith("20")]
    for inner_dir in inner_dirs:
        for item in inner_dir.iterdir():
            shutil.move(str(item), result_dir)
        shutil.rmtree(inner_dir)