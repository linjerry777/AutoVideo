import unittest

from scripts import business_finance_collector as collector


class BusinessFinanceCollectorTest(unittest.TestCase):
    def test_rejects_explicit_buy_sell_advice(self):
        item = {
            "title": "台股明天買進這三檔，目標價上看 200",
            "summary": "分析師建議加碼並停損。",
            "url": "https://example.com/buy",
        }

        self.assertTrue(collector.is_investment_advice(item))
        self.assertFalse(collector.passes_business_finance_gate(item))

    def test_scores_business_model_and_risk_items_above_generic_market_news(self):
        strong = {
            "title": "NVIDIA 的 AI 訂閱制正在改變公司商業模式",
            "summary": "拆解毛利、企業合約、雲端成本與市場風險。",
            "source": "example",
            "url": "https://example.com/nvidia-business",
        }
        weak = {
            "title": "今日台股收盤小漲",
            "summary": "大盤指數震盪，成交量持平。",
            "source": "example",
            "url": "https://example.com/market-close",
        }

        self.assertGreater(collector.score_candidate(strong), collector.score_candidate(weak) + 20)
        self.assertTrue(collector.passes_business_finance_gate(strong))
        self.assertFalse(collector.passes_business_finance_gate(weak))

    def test_builds_autovideo_ready_item_with_guardrails(self):
        item = collector.build_business_item({
            "title": "OpenAI 為什麼開始重視企業合約",
            "summary": "從訂閱制、雲端成本和現金流看 AI 公司怎麼賺錢。",
            "source": "Example News",
            "url": "https://example.com/openai-enterprise",
        })

        self.assertEqual(item["strategy"], "business_finance")
        self.assertEqual(item["source_type"], "business_finance")
        self.assertIn("非投資建議", item["analysis_guardrail"])
        self.assertIn("商業模式", item["hook"])
        self.assertGreaterEqual(item["media_ops_score"], 45)


if __name__ == "__main__":
    unittest.main()
