from math import ceil
from typing import List, Set, Tuple, Dict
from math import ceil
from typing import Dict, List, Tuple, Set
from vidur.entities.batch import Batch, Request
from vidur.scheduler.replica_scheduler.base_replica_scheduler import (
    BaseReplicaScheduler,
)

class BookingLimitReplicaScheduler(BaseReplicaScheduler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._preempted_requests: List[Request] = []
        self._num_running_batches = 0
        # For vLLM and its derivatives, we only need to set a loose max batch size
        # Memory requirements are handled explicitly by the scheduler
        self._max_micro_batch_size = self._config.batch_size_cap // self._num_stages
        self._watermark_blocks = int(
            self._config.watermark_blocks_fraction * self._config.num_blocks
        )

        self.total_limit = self._config.total_limit
        print("total_limit:", self.total_limit)
        self.total_num_requests = self._config.total_num_requests
        self.force_clear= self._config.force_clear
        if self.force_clear:
            print("会在最后强制清空队列")
        self.all_requests_arrived = False
        self.num_arrival_requests = 0 # 记录到达的请求数

        # 假设在此处初始化 prompt_types 信息，包括 type 和 arrival_rate 等
        # 示例数据，实际应从配置或其他地方获取

        a = 50
        # a 不会影响计算出来的booking_limit, 但是会影响总的到达速率

        self.prompt_types = [
            {"type": "type1", "prefill": 50, "decode": 156, "arrival_rate": 167*a},
            {"type": "type2", "prefill": 100, "decode": 171, "arrival_rate": 31*a},
            # 可继续添加其他类型...
        ]
        self.request_count_per_type = {pt["type"]: 0 for pt in self.prompt_types}

        self.booking_limits_per_type = self.calculate_booking_limits()
        print("Booking Limits Per Type:", self.booking_limits_per_type)
        for pt in self.prompt_types:
            num_stage = pt["decode"] + 1
            per_stage_limit = self.booking_limits_per_type[pt["type"]] / num_stage 
            per_stage_limit = max(per_stage_limit, 1)
            print(f"Type:{pt['type']}, per_stage_limit:{int(per_stage_limit)}")

    def add_request(self, request: Request) -> None:
        self._request_queue.append(request)
        self.num_arrival_requests += 1

        prompt_type = request.prompt_type  # 假设 request 具有 prompt_type 属性
        if prompt_type in self.request_count_per_type:
            self.request_count_per_type[prompt_type] += 1
        else:
            print(f"Warning: Received request with unknown type '{prompt_type}'")

        if self.num_arrival_requests == self.total_num_requests:
            self.all_requests_arrived = True
            print(f"计划到达个数:{self.total_num_requests}=已到达个数:{self.num_arrival_requests}")

            total_throughput = 0
            for prompt_type, count in self.request_count_per_type.items():
                print(f"Type:{prompt_type}, Count:{count}")
                prompt_info = next((pt for pt in self.prompt_types if pt["type"] == prompt_type), None)
                if prompt_info:
                    total_throughput += count * (prompt_info["decode"] + 1)
                else:
                    print(f"Warning: prompt_type '{prompt_type}' not found in self.prompt_types")
            print("理论上的throughput是:", total_throughput)

    def on_batch_end(self, batch: Batch) -> None:
        self._num_running_batches -= 1

        for request in batch.requests:
            if request.completed:
                self.free(request.id)
            else:
                self._preempted_requests.append(request)

    def _can_allocate_request(self, request: Request) -> bool:
        if request.id not in self._allocation_map:
            # new request
            num_required_blocks = ceil(
                (request.num_prefill_tokens) / self._config.block_size
            )
            return (
                self._config.num_blocks
                - self._num_allocated_blocks
                - num_required_blocks
                >= self._watermark_blocks
            )

        # vllm requires at least one block to be available
        return self._config.num_blocks - self._num_allocated_blocks >= 1

    def _allocate_request(self, request: Request) -> None:
        if request.id not in self._allocation_map:
            # new request
            num_required_blocks = ceil(
                (request.num_prefill_tokens) / self._config.block_size
            )
            self.allocate(request.id, num_required_blocks)
            return

        num_tokens_reserved = self._allocation_map[request.id] * self._config.block_size
        num_tokens_required = max(0, request.num_processed_tokens - num_tokens_reserved)
        assert (
            num_tokens_required == 0 or num_tokens_required == 1
        ), f"num_tokens_required: {num_tokens_required}"

        if num_tokens_required == 0:
            return

        self.allocate(request.id, 1)

    def calculate_booking_limits(self) -> Dict[str, int]:
        """
        计算每个类型的booking_limit。
        根据每种类型的arrival_rate按比例计算其在总limit中的分配。
        """
        # 获取每种类型的到达速率（arrival_rate）
        prompt_rates = {pt["type"]: pt["arrival_rate"] * (pt["decode"] +1) for pt in self.prompt_types}
        # prompt_rates = {pt["type"]: pt["arrival_rate"] for  pt in self.prompt_types}
        
        # 总到达速率
        total_rate = sum(prompt_rates.values())
        
        
        # 计算每个类型的 booking_limit
        booking_limits_per_type = {}
        for ptype, rate in prompt_rates.items():
            # 按比例分配到达速率
            booking_limits_per_type[ptype] = (rate / total_rate) * self.total_limit
            # booking_limits_per_type[ptype] = rate / total 
        #print(booking_limits_per_type)
        return booking_limits_per_type

    def _get_next_batch(self) -> Batch:
        # 先把上次未完成的请求重新加入主队列
        for req in self._preempted_requests:
            if req not in self._request_queue:
                self._request_queue.append(req)
        self._preempted_requests.clear()

        # 1. 将请求按 (prompt_type, current_stage) 分组
        grouped_requests: Dict[Tuple[str, int], List[Request]] = {}
        for req in self._request_queue:
            key = (getattr(req, 'prompt_type', 'default'), getattr(req, 'current_stage', 0))
            grouped_requests.setdefault(key, []).append(req)

        # 2. 为每种类型、每个阶段分配 booking limit
        prompt_stage_count = {pt["type"]: pt["decode"] + 1 for pt in self.prompt_types}        # 为每种类型、每个阶段分配 booking limit
        booking_limit: Dict[Tuple[str, int], int] = {}
        for ptype, limit in self.booking_limits_per_type.items():
            stages_for_type = prompt_stage_count.get(ptype, 0)
            per_stage_limit = limit / stages_for_type if stages_for_type > 0 else 0
            for stage in range(stages_for_type):
                booking_limit[(ptype, stage)] = int(max(per_stage_limit,1))

        # -------------- 只严格校验 stage=0 是否凑齐 --------------
        # 如果 stage=0 不够，则直接返回 None，不生成批次
        all_stage0_ready = True
        # print("Booking limits:", booking_limit)
        # print(booking_limit.get((ptype, 0), 0))
        # print("Booking Limits Per Type:", self.booking_limits_per_type)
        # print("Prompt Stage Count:", prompt_stage_count)
        # for ptype in prompt_rates.keys():
        for ptype  in self.booking_limits_per_type.keys():
            needed = booking_limit.get((ptype, 0), 0)
            available = len(grouped_requests.get((ptype, 0), []))
            if available < needed:
                all_stage0_ready = False
                break

    # 根据 new logic 修改分支判断：
        if not all_stage0_ready:
            if not self.all_requests_arrived:
                # 当 all_stage0_ready==False 且 all_requests_arrived==False，严格限制 stage0，返回 None
                return None
            else:
                # 当 all_stage0_ready==False 且 all_requests_arrived==True，强制清除队列
                print("所有请求已到达, 并且all_stage0_ready==False ,但强制清除队列")
                print("此时scheduler里面还剩下的request的数目是:", len(self._request_queue))
                for req in self._request_queue:
                    if req.id in self._allocation_map:
                        self.free(req.id)
                self._request_queue.clear()
                print("已经强制清空, 此时scheduler里面还剩下的request的数目是:", len(self._request_queue))
                return None

        # 若 all_stage0_ready 为 True，无论 all_requests_arrived 为 True 或 False，都按照 booking limit 选取请求构造批次
        selected_requests: List[Request] = []
        selected_num_tokens: List[int] = []

        # 对 stage=0，严格限制挑选数量不超过 booking_limit
        # 对 stage>0，直接拿全部可用（或可自行设置其他策略）
        for (ptype, stage), group in grouped_requests.items():
            if stage == 0:
                limit = booking_limit.get((ptype, 0), 0)
            else:
                limit = len(group)

            for _ in range(limit):
                if not group:
                    break
                req = group.pop(0)
                if req in self._request_queue:
                    self._request_queue.remove(req)
                self._allocate_request(req)
                # 推进请求阶段
                req.advance_stage()
                selected_requests.append(req)
                next_num = self._get_request_next_num_tokens(req)
                selected_num_tokens.append(next_num)

        if selected_requests:
            return Batch(self._replica_id, selected_requests, selected_num_tokens)
        return None
    
    def is_empty(self) -> bool:
        # 判断请求队列和正在执行或被抢占的请求是否都为空
        if self._request_queue:
            return False
        if self._preempted_requests:
            return False
        # 如果还有资源分配中但未完成的请求，也返回 False
        return True
