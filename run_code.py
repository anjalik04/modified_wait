import os
import subprocess
import shutil
from pathlib import Path

# Constants
min_base_limit = 25
max_base_limit = 180
base_window_range = [65,70,75]

prompt_types = [
    {"type": "type1", "prefill": 25, "decode": 25, "arrival_rate": 128},
    {"type": "type2", "prefill": 25, "decode": 75, "arrival_rate": 61},
    {"type": "type3", "prefill": 25, "decode": 125, "arrival_rate": 17},
    {"type": "type4", "prefill": 25, "decode": 175, "arrival_rate": 9}
]

trace_file = "data/processed_traces/mmpp2_four_types.csv"
results_root = "results"
os.makedirs(results_root, exist_ok=True)

for base in base_window_range:
    min_candidates = range(25, base-4, 5)
    r = list(range(base + 5, 180, 5))
    max_candidates = [x for x in r if x not in [135]]

    for min_w in min_candidates:
        for max_w in max_candidates:
            folder = f"window_test_min{min_w}_base{base}_max{max_w}"
            result_dir = os.path.join(results_root, folder)
            os.makedirs(result_dir, exist_ok=True)

            prompt_type_flag = str(prompt_types).replace("'", '"')

            command = [
                "python", "-m", "vidur.main",
                "--replica_config_device", "a100",
                "--replica_config_model_name", "meta-llama/Meta-Llama-3-8B",
                "--cluster_config_num_replicas", "1",
                "--replica_config_tensor_parallel_size", "1",
                "--replica_config_num_pipeline_stages", "1",
                "--request_generator_config_type", "trace_replay",
                "--replica_scheduler_config_type", "modified_general_nested_booking_limit",
                "--modified_general_nested_booking_limit_scheduler_config_prompt_types", prompt_type_flag,
                "--modified_general_nested_booking_limit_scheduler_config_total_limit", "128",
                "--modified_general_nested_booking_limit_scheduler_config_force_clear",
                "--random_forrest_execution_time_predictor_config_prediction_max_prefill_chunk_size", "16384",
                "--random_forrest_execution_time_predictor_config_prediction_max_batch_size", "2048",
                "--random_forrest_execution_time_predictor_config_prediction_max_tokens_per_request", "16384",
                "--trace_request_generator_config_trace_file", trace_file,
                "--modified_general_nested_booking_limit_scheduler_config_min_window", str(min_w),
                "--modified_general_nested_booking_limit_scheduler_config_base_window", str(base),
                "--modified_general_nested_booking_limit_scheduler_config_max_window", str(max_w),
                "--metrics_config_output_dir", result_dir
            ]

            print(f"[Running] {result_dir}")

            # Run and capture logs
            with open(f"{result_dir}/output.log", "w") as outfile:
                subprocess.run(command, stdout=outfile, stderr=subprocess.STDOUT)

            # Flatten output if timestamp folder is created
            inner_dirs = [d for d in Path(result_dir).iterdir() if d.is_dir() and d.name.startswith("20")]
            if inner_dirs:
                output_subdir = inner_dirs[0]
                for item in output_subdir.iterdir():
                    shutil.move(str(item), result_dir)
                shutil.rmtree(output_subdir)
