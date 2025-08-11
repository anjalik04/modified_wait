from math import ceil
from statistics import mean
from typing import List, Dict, Tuple
from vidur.entities.batch import Batch, Request
from vidur.scheduler.replica_scheduler.base_replica_scheduler import BaseReplicaScheduler

class ArrivalRateUpdateGeneralizedNestedBookingLimitReplicaScheduler(BaseReplicaScheduler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._preempted_requests: List[Request] = []
        self._num_running_batches = 0

        self.total_limit = self._config.total_limit
        self.total_num_requests = self._config.total_num_requests
        self.force_clear = self._config.force_clear
        self.all_requests_arrived = False
        self.num_arrival_requests = 0

        self.prompt_types = self._config.prompt_types
        self.arrival_rate_updates = {pt["type"]: [] for pt in self.prompt_types}

        self.nested_booking_limits, self.segments = self.calculate_nested_booking_limits()

    def _update_arrival_rate_and_booking_limits(self):
        for pt in self.prompt_types:
            pt_type = pt["type"]
            updates = self.arrival_rate_updates[pt_type]
            if updates:
                pt["arrival_rate"] = mean(updates)

        self.nested_booking_limits, self.segments = self.calculate_nested_booking_limits()

    def add_request(self, request: Request) -> None:
        self._request_queue.append(request)
        self.num_arrival_requests += 1

        if hasattr(request, "prompt_type") and hasattr(request, "arrival_rate_update"):
            pt_type = request.prompt_type
            if pt_type in self.arrival_rate_updates:
                self.arrival_rate_updates[pt_type].append(request.arrival_rate_update)
                self._update_arrival_rate_and_booking_limits()

        if self.num_arrival_requests == self.total_num_requests:
            self.all_requests_arrived = True

    def calculate_nested_booking_limits(self) -> Tuple[Dict[int, int], List[Dict[str, int]]]:
        unique_decodes = sorted({pt["decode"] for pt in self.prompt_types})
        segments = []

        seg1_count = unique_decodes[0]
        seg1_arrival_sum = sum(pt["arrival_rate"] for pt in self.prompt_types)
        segments.append({"count": seg1_count, "arrival_sum": seg1_arrival_sum})

        for i in range(1, len(unique_decodes)):
            stage_count = unique_decodes[i] - unique_decodes[i - 1]
            seg_arrival_sum = sum(pt["arrival_rate"] for pt in self.prompt_types if pt["decode"] > unique_decodes[i - 1])
            segments.append({"count": stage_count, "arrival_sum": seg_arrival_sum})

        total_weight = sum(seg["count"] * seg["arrival_sum"] for seg in segments)

        nested_booking_limits = {}
        segment_metadata = []
        global_stage = 0
        for seg in segments:
            seg_weight = seg["count"] * seg["arrival_sum"]
            seg_total_limit = self.total_limit * (seg_weight / total_weight) if total_weight > 0 else 0
            per_stage_limit = ceil(seg_total_limit / seg["count"])

            seg_start = global_stage
            for _ in range(seg["count"]):
                nested_booking_limits[global_stage] = per_stage_limit
                global_stage += 1

            seg_end = global_stage - 1
            segment_metadata.append({
                "start": seg_start,
                "end": seg_end,
                "per_stage_limit": per_stage_limit,
                "seg_total_limit": int(seg_total_limit)
            })

        return nested_booking_limits, segment_metadata

   
    def _allocate_request(self, request: Request) -> None:
        """
        分配资源给 request。
        - 如果是新请求，则根据其 prefill tokens 计算所需 block 数量进行分配；
        - 如果 request 已存在，则按需额外分配 1 个 block。
        """
        if request.id not in self._allocation_map:
            num_required_blocks = ceil(request.num_prefill_tokens / self._config.block_size)
            self.allocate(request.id, num_required_blocks)
        else:
            num_tokens_reserved = self._allocation_map[request.id] * self._config.block_size
            num_tokens_required = max(0, request.num_processed_tokens - num_tokens_reserved)
            if num_tokens_required:
                self.allocate(request.id, 1)
   
    def _get_next_batch(self) -> Batch:
        """
        调度逻辑：
          1. 将上次未完成的请求(preempted)重新归入队列;
          2. 按 request.current_stage(全局 stage)将请求分组;
          3. 按 segments 顺序依次调度：
             - 对于每个 segment, 首先检查该 segment 起始 stage 上的请求数是否达到预设的 booking limit(即 nested_booking_limits[segment.start])
             - 只有当前一段已经启动后，后续 segment 才允许启动;
             - 对于满足条件的 segment,从该段内每个 stage中各取出不超过预设 limit 数量的请求
               并调用 _allocate_request() 以及 req.advance_stage() 使请求进入下一阶段
          4. 将选中的请求打包成一个 Batch 返回
       
        调度逻辑修改说明：
        - 如果 self.all_requests_arrived 为 False,则沿用原有的顺序调度逻辑
        - 如果 self.all_requests_arrived 为 True,则逐个检查每个 segment 的起始阶段(seg["start"])是否满足预设的 booking limit
            (1) 如果至少有一个 segment 的起始阶段满足条件, 则对所有满足条件的 segment 进行调度
                即从该 segment 内各个阶段中各自取出不超过预设 limit 的请求
            (2) 如果所有 segment 的起始阶段都不满足预设条件, 则执行强制清空队列的逻辑
                打印相关信息, 释放已分配资源, 并清空 _request_queue, 最后返回 None
        """
        # 将上次未完成的（preempted）请求重新归入队列
        for req in self._preempted_requests:
            if req not in self._request_queue:
                self._request_queue.append(req)
        self._preempted_requests.clear()


        # 按请求的 current_stage 将请求分组
        grouped_requests: Dict[int, List[Request]] = {}
        for req in self._request_queue:
            stage = getattr(req, 'current_stage', 0)
            grouped_requests.setdefault(stage, []).append(req)


        selected_requests: List[Request] = []
        selected_num_tokens: List[int] = []


        first_segment_satisfied = False
        first_segment = self.segments[0]
        firts_seg_start = first_segment["start"]
        # required 是第一个限制, 是之前严格的booking limit限制
        required = self.nested_booking_limits.get(firts_seg_start, 0)
        # occupied 是当前在这个segment但不在初始位置的请求的数目, 也是已经被占用的limit
        occupied = sum(1 for req in self._request_queue
                   if getattr(req, 'current_stage', 0) > first_segment["start"]
                   and getattr(req, 'current_stage', 0)<= first_segment["end"])
        # limit_for_this_segment 是这个segment的limit
        limit_for_this_segment = first_segment["seg_total_limit"]
        # remain 是剩余的limit
        remain = limit_for_this_segment - occupied
        stage_0_num = len(grouped_requests.get(firts_seg_start, []))
        #print(f"\nlimit_for_first_segment={limit_for_this_segment},  occupied={occupied},  remain={remain},  required_limit={required},  stage_0_num={stage_0_num}")


        #
        # if len(grouped_requests.get(firts_seg_start, [])) >= min(required, remain):
        #     first_segment_satisfied = True


        # 不要下限
        first_segment_satisfied = True
        # 根据 all_requests_arrived 标识分两种逻辑
        # if not self.all_requests_arrived:
        #print("\n\n\n")
        if not self.all_requests_arrived or (self.all_requests_arrived and first_segment_satisfied):
            # 原有逻辑：依次检查各个 segment，要求前一个 segment 必须满足条件才能启动后续 segment
            # 现在修改成了: 要么所有请求还没有到达, 要么已经全部到达但是第一个segment满足了
            seg_num = 0
            for seg in self.segments:
                seg_num += 1
                seg_start = seg["start"]
                required = self.nested_booking_limits.get(seg_start, 0)
                occupied = sum(1 for req in self._request_queue
                    if getattr(req, 'current_stage', 0) > seg["start"]
                    and getattr(req, 'current_stage', 0) <= seg["end"])
                limit_for_this_segment = seg["seg_total_limit"]
                # print(limit_for_this_segment)
                remain = limit_for_this_segment - occupied
                # print(f"start={seg_start}, end={seg["end"]}, required={required}, occupied={occupied}, remain={remain}, limit_for_this_segment={limit_for_this_segment}, start_num={len(grouped_requests.get(seg_start, []))}")
                # if seg == self.segments[-1] and len(grouped_requests.get(seg_start, [])) >= min(required, remain):
                #     print(f"一共启动了{seg_num}个segment")
                if len(grouped_requests.get(seg_start, [])) < min(required, remain):
                    # 如果该 segment 的起始阶段请求数不够，则不启动后续 segment
                    #print(f"一共启动了{seg_num-1}个segment")
                    break


                #print("\n")
                # 对该 segment 内每个阶段调度请求
                for stage in range(seg["start"], seg["end"] + 1):
                    required = self.nested_booking_limits.get(stage, 0)
                   
                    if stage == seg["start"]:
                        limit = min(remain, required)
                    else:
                        limit = self.nested_booking_limits.get(stage, 0)
                    #if stage == 0:
                    #    limit -= int(limit*0.4)
                        #print("CAUTION! STAGE 0!!!")
                    #print(f"stage={stage}, limit={limit}, allocated_blocks = {self._config.num_blocks -  self.num_allocated_blocks}")
                    group = grouped_requests.get(stage, [])
                    for _ in range(limit):
                        if not group:
                            break
                        req = group.pop(0)
                        if req in self._request_queue:
                            self._request_queue.remove(req)
                        self._allocate_request(req)
                        req.advance_stage()
                        selected_requests.append(req)
                        next_num = self._get_request_next_num_tokens(req)
                        selected_num_tokens.append(next_num)
        else:
            # # 新逻辑：所有请求已到达
            # found_segment = False  # 标记是否有至少一个 segment 的起始阶段满足 booking limit
            # for seg in self.segments:
            #     seg_start = seg["start"]
            #     required = self.nested_booking_limits.get(seg_start, 0)
            #     if len(grouped_requests.get(seg_start, [])) >= required:
            #         # 如果该 segment 的起始阶段满足预设条件，则进行调度
            #         found_segment = True
            #         for stage in range(seg["start"], seg["end"] + 1):
            #             limit = self.nested_booking_limits.get(stage, 0)
            #             group = grouped_requests.get(stage, [])
            #             for _ in range(limit):
            #                 if not group:
            #                     break
            #                 req = group.pop(0)
            #                 if req in self._request_queue:
            #                     self._request_queue.remove(req)
            #                 self._allocate_request(req)
            #                 req.advance_stage()
            #                 selected_requests.append(req)
            #                 next_num = self._get_request_next_num_tokens(req)
            #                 selected_num_tokens.append(next_num)
            #     # 对于不满足条件的 segment，不进行处理break


            # if not found_segment:
            #     # 如果所有 segment 的起始阶段都不满足 booking limit，则执行强制清空队列逻辑
                print("所有请求已到达, 但是第一个segment不够, 所以都不能运行了 ,强制清除队列")
                print("此时scheduler里面还剩下的request的数目是:", len(self._request_queue))
                for req in self._request_queue:
                    if req.id in self._allocation_map:
                        self.free(req.id)
                self._request_queue.clear()
                print("已经强制清空, 此时scheduler里面还剩下的request的数目是:", len(self._request_queue))
                return None


        if selected_requests:
            return Batch(self._replica_id, selected_requests, selected_num_tokens)
        return None
   
    def on_batch_end(self, batch: Batch) -> None:
        """
        批次执行结束后：
          - 若请求已完成，则释放资源；
          - 否则将其加入 preempted 队列，待下次调度时重新归队。
        """
        self._num_running_batches -= 1
        for request in batch.requests:
            if request.completed:
                self.free(request.id)
            else:
                self._preempted_requests.append(request)
   
    def is_empty(self) -> bool:
        """
        判断队列和 preempted 请求是否均为空。
        """
        return not self._request_queue and not self._preempted_requests