#!/usr/bin/env python3
"""Business-finance candidate scoring for AutoVideo.

This lane is for business-model and market-risk explainers, not stock tips.
It deliberately avoids buy/sell/target-price language so the generated account
can stay in a safer "business analysis" posture.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))


BUSINESS_TERMS = (
    "business model",
    "revenue",
    "margin",
    "subscription",
    "enterprise",
    "earnings",
    "guidance",
    "cash flow",
    "pricing",
    "商業模式",
    "營收",
    "毛利",
    "訂閱",
    "企業合約",
    "財報",
    "現金流",
    "成本",
    "變現",
    "風險",
    "護城河",
)

COMPANY_TERMS = (
    "nvidia",
    "openai",
    "microsoft",
    "google",
    "meta",
    "apple",
    "tesla",
    "tsmc",
    "台積電",
    "輝達",
    "微軟",
    "谷歌",
    "蘋果",
)

ADVICE_TERMS = (
    "買進",
    "賣出",
    "加碼",
    "減碼",
    "停損",
    "停利",
    "目標價",
    "明天買",
    "必買",
    "buy rating",
    "sell rating",
    "price target",
    "stop loss",
)

GENERIC_MARKET_TERMS = (
    "收盤",
    "小漲",
    "小跌",
    "震盪",
    "成交量",
    "大盤",
    "指數",
)


def compact_text(*parts: Any) -> str:
    return re.sub(r"\s+", " ", " ".join(str(p or "") for p in parts)).strip()


def is_investment_advice(item: dict[str, Any]) -> bool:
    text = compact_text(item.get("title"), item.get("summary")).lower()
    return any(term.lower() in text for term in ADVICE_TERMS)


def score_candidate(item: dict[str, Any]) -> int:
    text = compact_text(item.get("title"), item.get("summary"), item.get("source")).lower()
    score = 18
    score += min(36, sum(1 for term in BUSINESS_TERMS if term.lower() in text) * 8)
    score += min(18, sum(1 for term in COMPANY_TERMS if term.lower() in text) * 6)
    score += min(12, len(re.findall(r"\d+(?:\.\d+)?\s*[%億兆萬]?", text)) * 3)
    if any(term.lower() in text for term in ("ai", "人工智慧", "雲端", "晶片", "半導體")):
        score += 8
    score -= min(24, sum(1 for term in GENERIC_MARKET_TERMS if term in text) * 6)
    if is_investment_advice(item):
        score -= 50
    if not item.get("url"):
        score -= 8
    return max(0, min(100, score))


def passes_business_finance_gate(item: dict[str, Any], threshold: int = 45) -> bool:
    return not is_investment_advice(item) and score_candidate(item) >= threshold


def build_business_item(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    summary = str(item.get("summary") or item.get("description") or title).strip()
    source = str(item.get("source") or item.get("source_name") or "Business source").strip()
    url = str(item.get("url") or item.get("source_url") or "").strip()
    score = score_candidate(item)
    hook = _hook_for(title, summary)
    return {
        "strategy": "business_finance",
        "title": title,
        "raw_title": title,
        "summary": summary,
        "hook": hook,
        "source": source,
        "source_name": source,
        "url": url,
        "source_url": url,
        "source_type": "business_finance",
        "media_ops_topic": "business_finance",
        "media_ops_cluster": _cluster_for(title, summary),
        "media_ops_source_key": source.lower(),
        "media_ops_score": score,
        "media_ops_virality_score": min(40, max(0, score - 35)),
        "analysis_guardrail": "非投資建議；只做商業模式、公司風險與市場結構解讀。",
    }


def _hook_for(title: str, summary: str) -> str:
    text = compact_text(title, summary)
    if any(term in text for term in ("商業模式", "business model", "訂閱", "subscription")):
        return "商業模式才是重點"
    if any(term in text for term in ("風險", "成本", "cash flow", "現金流")):
        return "真正風險在這裡"
    return "這家公司怎麼賺錢"


def _cluster_for(title: str, summary: str) -> str:
    text = compact_text(title, summary).lower()
    for company in COMPANY_TERMS:
        if company.lower() in text:
            return f"business_finance:{company.lower()}"
    return "business_finance:general"


def rank_candidates(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ready = [build_business_item(item) for item in items if passes_business_finance_gate(item)]
    ready.sort(key=lambda x: (x.get("media_ops_score") or 0, x.get("title") or ""), reverse=True)
    return ready[:limit]


def collect_candidates(
    *,
    keywords: list[str] | None = None,
    sources: list[str] | None = None,
    limit: int = 5,
    fetcher: Callable[..., list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    if fetcher is None:
        from web.routes.news import _fetch_all as fetcher

    keywords = keywords or ["AI business model", "科技財經", "商業模式"]
    sources = sources or ["google", "bing", "hackernews", "ithome", "last30days"]
    raw: list[dict[str, Any]] = []
    seen: set[str] = set()
    for keyword in keywords:
        try:
            batch = fetcher(keyword=keyword, lang="zh-TW", sources=sources) or []
        except TypeError:
            batch = fetcher(keyword, sources) or []
        except Exception:
            batch = []
        for item in batch:
            url = str(item.get("url") or item.get("source_url") or "")
            key = url or compact_text(item.get("title"), item.get("summary"))
            if key and key not in seen:
                seen.add(key)
                raw.append(item)
    return rank_candidates(raw, limit=limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--keywords", default="AI business model,科技財經,商業模式")
    parser.add_argument("--sources", default="google,bing,hackernews,ithome,last30days")
    args = parser.parse_args()
    items = collect_candidates(
        keywords=[x.strip() for x in args.keywords.split(",") if x.strip()],
        sources=[x.strip() for x in args.sources.split(",") if x.strip()],
        limit=args.limit,
    )
    print(json.dumps({"strategy": "business_finance", "items": items}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
