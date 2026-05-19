"""
Token 和成本估算工具
"""
from decimal import Decimal
from typing import Optional


class CostCalculator:
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """简单估算 token 数"""
        if not text:
            return 0
        return max(len(text) // 4, 1)

    @staticmethod
    def calculate_cost(
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        input_price: Optional[Decimal],
        output_price: Optional[Decimal]
    ) -> Decimal:
        """按每百万 tokens 价格估算成本"""
        del model_name
        prompt_price = Decimal(str(input_price or 0))
        completion_price = Decimal(str(output_price or 0))
        cost = Decimal(input_tokens) / Decimal('1000000') * prompt_price
        cost += Decimal(output_tokens) / Decimal('1000000') * completion_price
        return cost.quantize(Decimal('0.000001'))
