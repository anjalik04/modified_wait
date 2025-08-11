from vidur.scheduler.replica_scheduler.faster_transformer_replica_scheduler import (
    FasterTransformerReplicaScheduler,
)
from vidur.scheduler.replica_scheduler.lightllm_replica_scheduler import (
    LightLLMReplicaScheduler,
)
from vidur.scheduler.replica_scheduler.orca_replica_scheduler import (
    OrcaReplicaScheduler,
)
from vidur.scheduler.replica_scheduler.sarathi_replica_scheduler import (
    SarathiReplicaScheduler,
)
from vidur.scheduler.replica_scheduler.vllm_replica_scheduler import (
    VLLMReplicaScheduler,
)
from vidur.scheduler.replica_scheduler.booking_limit_replica_scheduler import BookingLimitReplicaScheduler
from vidur.scheduler.replica_scheduler.nested_booking_limit_replica_scheduler import NestedBookingLimitReplicaScheduler
from vidur.scheduler.replica_scheduler.general_nested_booking_limit_replica_scheduler import GeneralizedNestedBookingLimitReplicaScheduler
from vidur.scheduler.replica_scheduler.modified_booking_limit_replica_scheduler import ModifiedBookingLimitReplicaScheduler
from vidur.scheduler.replica_scheduler.our_modified_booking_limit_replica_scheduler import OurModifiedBookingLimitReplicaScheduler
from vidur.scheduler.replica_scheduler.modified_general_nested_booking_limit_replica_scheduler import ModifiedGeneralizedNestedBookingLimitReplicaScheduler
from vidur.scheduler.replica_scheduler.arrival_rate_update_general_nested_booking_limit_replica_scheduler import ArrivalRateUpdateGeneralizedNestedBookingLimitReplicaScheduler


from vidur.types.replica_scheduler_type import ReplicaSchedulerType
from vidur.types import ReplicaSchedulerType
from vidur.utils.base_registry import BaseRegistry


class ReplicaSchedulerRegistry(BaseRegistry):
    pass


ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.FASTER_TRANSFORMER, FasterTransformerReplicaScheduler
)
ReplicaSchedulerRegistry.register(ReplicaSchedulerType.ORCA, OrcaReplicaScheduler)
ReplicaSchedulerRegistry.register(ReplicaSchedulerType.SARATHI, SarathiReplicaScheduler)
ReplicaSchedulerRegistry.register(ReplicaSchedulerType.VLLM, VLLMReplicaScheduler)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.LIGHTLLM, LightLLMReplicaScheduler
)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.BOOKING_LIMIT, BookingLimitReplicaScheduler
)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.NESTED_BOOKING_LIMIT, NestedBookingLimitReplicaScheduler
)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.GENERAL_NESTED_BOOKING_LIMIT,
    GeneralizedNestedBookingLimitReplicaScheduler,
)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.MODIFIED_BOOKING_LIMIT,
    ModifiedBookingLimitReplicaScheduler,
)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.OUR_MODIFIED_BOOKING_LIMIT,
    OurModifiedBookingLimitReplicaScheduler,
)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.MODIFIED_GENERAL_NESTED_BOOKING_LIMIT,
    ModifiedGeneralizedNestedBookingLimitReplicaScheduler
)
ReplicaSchedulerRegistry.register(
    ReplicaSchedulerType.ARRIVAL_RATE_UPDATE_GENERAL_NESTED_BOOKING_LIMIT,
    ArrivalRateUpdateGeneralizedNestedBookingLimitReplicaScheduler
)