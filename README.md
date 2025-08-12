
# Modified WAIT

This repository implements the experiments and code for the paper “LLM Inference Under Bursty Workload Distribution: Modifying the WAIT Algorithm.”
It is a fork of the [vidur_or](https://github.com/Luoxiaogan/vidur_or.git) project (https://github.com/Luoxiaogan/vidur_or.git) and extends that baseline implementation — Optimizing LLM Inference: Fluid-Guided Online Scheduling with Memory Constraints — with our modifications to the WAIT scheduling policy to better handle bursty workloads and memory constraints.

**What’s included**:
1. Reproductions of the baseline scheduling and simulation code from vidur_or.
2. Our modified WAIT scheduler implementation and experiment scripts.
3. Scripts to run synthetic and real-world MMPP traces, collect metrics (throughput, response time, peak memory), and reproduce figures from the paper.
