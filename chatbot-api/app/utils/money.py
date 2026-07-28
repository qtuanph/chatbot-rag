from __future__ import annotations

from app.core.config import settings

MICROS_PER_VND = 1_000_000
HALF_VND_MICROS = MICROS_PER_VND // 2


def compute_cost_micros_vnd(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    input_price_vnd_per_1m: int | None = None,
    output_price_vnd_per_1m: int | None = None,
) -> int:
    if input_price_vnd_per_1m is None or output_price_vnd_per_1m is None:
        try:
            from app.modules.settings.runtime_manager import RuntimeProviderManager
            rtm = RuntimeProviderManager.get_instance()
            if input_price_vnd_per_1m is None:
                input_price_vnd_per_1m = int(rtm.get_billing("ai_input_price_vnd_per_1m", "0")) or settings.ai_input_price_vnd_per_1m
            if output_price_vnd_per_1m is None:
                output_price_vnd_per_1m = int(rtm.get_billing("ai_output_price_vnd_per_1m", "0")) or settings.ai_output_price_vnd_per_1m
        except Exception:
            if input_price_vnd_per_1m is None:
                input_price_vnd_per_1m = settings.ai_input_price_vnd_per_1m
            if output_price_vnd_per_1m is None:
                output_price_vnd_per_1m = settings.ai_output_price_vnd_per_1m

    input_rate = input_price_vnd_per_1m
    output_rate = output_price_vnd_per_1m
    return max(0, (int(prompt_tokens) * int(input_rate)) + (int(completion_tokens) * int(output_rate)))


def micros_vnd_to_decimal_string(amount_micros: int) -> str:
    sign = "-" if amount_micros < 0 else ""
    absolute = abs(int(amount_micros))
    whole = absolute // MICROS_PER_VND
    fraction = absolute % MICROS_PER_VND
    if fraction == 0:
        return f"{sign}{whole}"
    fraction_str = f"{fraction:06d}".rstrip("0")
    return f"{sign}{whole}.{fraction_str}"


def micros_vnd_to_rounded_vnd(amount_micros: int) -> int:
    absolute = abs(int(amount_micros))
    rounded = (absolute + HALF_VND_MICROS) // MICROS_PER_VND
    return -rounded if amount_micros < 0 else rounded


def build_money_payload(amount_micros: int) -> dict[str, int | str]:
    return {
        "currency_code": settings.billing_currency_code,
        "cost_micros_vnd": int(amount_micros),
        "cost_vnd": micros_vnd_to_decimal_string(amount_micros),
        "cost_vnd_rounded": micros_vnd_to_rounded_vnd(amount_micros),
    }
