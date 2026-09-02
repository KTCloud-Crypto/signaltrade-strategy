from signaltrade_strategy.catalog import MARKET_CATALOG, STRATEGY_CATALOG, seed_strategy_catalog
from signaltrade_strategy.database import Base, SessionLocal, engine
from signaltrade_strategy.models import Strategy, SupportedMarket


def test_catalog_seeds_all_markets_and_strategies() -> None:
    with SessionLocal() as db:
        seed_strategy_catalog(db)
        assert db.query(SupportedMarket).count() == len(MARKET_CATALOG)
        assert db.query(Strategy).count() == len(STRATEGY_CATALOG)
        assert {row.code for row in db.query(Strategy)} == {
            definition["code"] for definition in STRATEGY_CATALOG
        }
