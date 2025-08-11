from vidur.config.config import SimulationConfig
from vidur.simulator import Simulator
from vidur.utils.random import set_seeds


def main() -> None:
    print(SimulationConfig)
    config: SimulationConfig = SimulationConfig.create_from_cli_args()
    print(config)

    set_seeds(config.seed)
    print(Simulator)
    simulator = Simulator(config)
    print(simulator)
    simulator.run()


if __name__ == "__main__":
    main()
