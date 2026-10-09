"""Customer-facing nomenclature for Robocheki SMZ (internal tier codes unchanged)."""


def receipt_item_name(order_number, plan, purpose):
    if plan.access_tier == "device_slots":
        counts = {"device_slots_1": 1, "device_slots_2": 2, "device_slots_3": 3}
        count = counts.get(plan.code)
        if count is None:
            raise ValueError("Unknown device slot package")
        service = ("подключение дополнительного устройства" if count == 1
                   else f"подключение дополнительных устройств ({count})")
    else:
        tiers = {"basic": "Basic", "mobile": "Pro"}
        if plan.access_tier not in tiers:
            raise ValueError("Unknown subscription tier")
        service = f"{'подарочная подписка' if purpose == 'gift' else 'подписка'} {tiers[plan.access_tier]}"
    return f"Оплата заказа №{order_number}, {service}"


def subscription_term(days):
    return {7: "7 дней", 30: "1 месяц", 90: "3 месяца", 180: "6 месяцев",
            360: "12 месяцев", 365: "12 месяцев"}.get(days, f"{days} дней")


def checkout_description(plan, purpose):
    if plan.access_tier == "device_slots":
        count = {"device_slots_1": 1, "device_slots_2": 2, "device_slots_3": 3}.get(plan.code)
        if count is None:
            raise ValueError("Unknown device slot package")
        return f"Покупка дополнительного устройства - {count}"
    tier = {"basic": "Basic", "mobile": "Pro"}[plan.access_tier]
    title = "Подарочная подписка" if purpose == "gift" else "Подписка"
    return f"{title} {tier} - {subscription_term(plan.duration_days)}"
