import importlib.util
import sqlite3
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "ops/xray/mobile_usage_collector.py"
spec = importlib.util.spec_from_file_location("mobile_usage_collector", SCRIPT)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_only_mobile_counters_are_accounted(tmp_path):
    counters = collector.parse_counters({"stat": [
        {"name": "user>>>mobile_a@workplayvpn>>>traffic>>>downlink", "value": "120"},
        {"name": "user>>>mobile_a@workplayvpn>>>traffic>>>uplink", "value": "30"},
        {"name": "user>>>regular@workplayvpn>>>traffic>>>downlink", "value": "500"},
    ]})
    assert len(counters) == 2
    database = sqlite3.connect(tmp_path / "usage.sqlite")
    collector.record_snapshot(database, 100, counters)
    collector.record_snapshot(database, 100, counters)
    updated = dict(counters)
    updated["user>>>mobile_a@workplayvpn>>>traffic>>>downlink"] = 200
    collector.record_snapshot(database, 100, updated)
    collector.record_snapshot(database, 101, {
        "user>>>mobile_a@workplayvpn>>>traffic>>>downlink": 15,
    })
    totals = dict(database.execute("SELECT name, total FROM counters"))
    assert totals["user>>>mobile_a@workplayvpn>>>traffic>>>downlink"] == 215
    assert totals["user>>>mobile_a@workplayvpn>>>traffic>>>uplink"] == 30


def test_candidate_preserves_existing_api_and_transport():
    source = Path(__file__).resolve().parents[2] / "ops/xray/prepare_mobile_stats.py"
    candidate_spec = importlib.util.spec_from_file_location("prepare_mobile_stats", source)
    module = importlib.util.module_from_spec(candidate_spec)
    candidate_spec.loader.exec_module(module)
    config = {
        "api": {"listen": "127.0.0.1:10086", "services": ["HandlerService"]},
        "inbounds": [{"tag": "vless-yandex-cdn-test", "port": 9445}],
        "policy": {"levels": {"0": {"connectionIdle": 300}}},
    }
    candidate = module.with_mobile_stats(config)
    assert config["api"]["services"] == ["HandlerService"]
    assert candidate["api"]["services"] == ["HandlerService", "StatsService"]
    assert candidate["inbounds"] == config["inbounds"]
    assert candidate["policy"]["levels"]["0"]["connectionIdle"] == 300
    assert candidate["policy"]["levels"]["0"]["statsUserDownlink"] is True
