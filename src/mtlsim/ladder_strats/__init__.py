from ._base import (
    BaseLadderStrategy,
    StrategyDecision,
    StrategyDecisionAddLeaves,
    StrategyDecisionCreateLadder,
)
from .oneladder_infgrow import OneLadderInfGrowStrategy
from .oneladder_max_stale import OneLadderMaxStaleStrategy
from .oneladder_max_time import OneLadderMaxTimeStrategy

__all__ = (
    "BaseLadderStrategy",
    "StrategyDecision",
    "StrategyDecisionAddLeaves",
    "StrategyDecisionCreateLadder",
    "OneLadderInfGrowStrategy",
    "OneLadderMaxTimeStrategy",
    "OneLadderMaxStaleStrategy",
)


def get_strategies() -> dict[str, type[BaseLadderStrategy]]:
    return {
        strat_cls.STRATEGY_ID: strat_cls
        for strat_cls in BaseLadderStrategy.__subclasses__()
    }


def get_strategy_by_id(
    strategy_id: str,
    params: dict[str, str],
) -> BaseLadderStrategy | None:
    strat_cls = get_strategies().get(strategy_id)
    if strat_cls is None:
        return None

    missing_params = strat_cls.STRATEGY_PARAMS.keys() - params.keys()
    extra_params = params.keys() - strat_cls.STRATEGY_PARAMS.keys()
    if missing_params or extra_params:
        raise ValueError(
            f"Invalid parameters for strategy {strategy_id} (missing: {missing_params}, extra: {extra_params})"
        )

    return strat_cls(
        **{
            param: strat_cls.STRATEGY_PARAMS[param](params[param])
            for param in strat_cls.STRATEGY_PARAMS
        }
    )
