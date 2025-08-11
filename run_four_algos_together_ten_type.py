import subprocess
import os
import json
import shutil
from pathlib import Path

# ================= USER-DEFINED VARIABLES ====================
trace_file = "data/processed_traces/high_rate_ten_type_mmpp2.csv"

prompt_types = [
    {"type": "type1", "prefill": 100, "decode": 25, "arrival_rate": 901},
    {"type": "type2", "prefill": 100, "decode": 50, "arrival_rate": 823},
    {"type": "type1", "prefill": 100, "decode": 100, "arrival_rate": 758},
    {"type": "type2", "prefill": 100, "decode": 200, "arrival_rate": 647},
    {"type": "type1", "prefill": 100, "decode": 400, "arrival_rate": 546},
    {"type": "type2", "prefill": 100, "decode": 500, "arrival_rate": 464},
    {"type": "type1", "prefill": 100, "decode": 600, "arrival_rate": 382},
    {"type": "type2", "prefill": 100, "decode": 700, "arrival_rate": 263},
    {"type": "type1", "prefill": 100, "decode": 800, "arrival_rate": 180},
    {"type": "type2", "prefill": 100, "decode": 900, "arrival_rate": 91},
]

prompt_type_flag = json.dumps(prompt_types)
batch_size = 128
booking_limit = 128
results_root = "results_4_tests_two_types"
# =============================================================

os.makedirs(results_root, exist_ok=True)

tests = [
    {
        "name": "modified_nested_wait",
        "command": [
            "--replica_scheduler_config_type", "modified_general_nested_booking_limit",
            "--modified_general_nested_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
            "--modified_general_nested_booking_limit_scheduler_config_total_limit", str(booking_limit),
            "--modified_general_nested_booking_limit_scheduler_config_force_clear"
        ]
    },
    {
        "name": "nested_wait",
        "command": [
            "--replica_scheduler_config_type", "general_nested_booking_limit",
            "--general_nested_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
            "--general_nested_booking_limit_scheduler_config_total_limit", str(booking_limit),
            "--general_nested_booking_limit_scheduler_config_force_clear"
        ]
    },
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
    {   
        "name": "arrival_rate_update_nested_wait",
        "command": [
            "--replica_scheduler_config_type", "arrival_rate_update_general_nested_booking_limit",
            "--arrival_rate_update_general_nested_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
            "--arrival_rate_update_general_nested_booking_limit_scheduler_config_total_limit", str(booking_limit),
            "--arrival_rate_update_general_nested_booking_limit_scheduler_config_force_clear"
        ]
    },
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