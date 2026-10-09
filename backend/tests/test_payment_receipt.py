from types import SimpleNamespace
import pytest
from app.services.payment_receipt import receipt_item_name

@pytest.mark.parametrize('tier,purpose,code,expected', [
    ('basic', 'subscription', 'standard_1m', 'подписка Basic'),
    ('mobile', 'subscription', 'mobile_1m', 'подписка Pro'),
    ('basic', 'gift', 'standard_1m', 'подарочная подписка Basic'),
    ('mobile', 'gift', 'mobile_1m', 'подарочная подписка Pro'),
    ('device_slots', 'subscription', 'device_slots_1', 'подключение дополнительного устройства'),
    ('device_slots', 'subscription', 'device_slots_2', 'подключение дополнительных устройств (2)'),
    ('device_slots', 'subscription', 'device_slots_3', 'подключение дополнительных устройств (3)'),
])
def test_receipt_names(tier, purpose, code, expected):
    plan = SimpleNamespace(access_tier=tier, code=code)
    result = receipt_item_name('947031557604', plan, purpose)
    assert result == f'Оплата заказа №947031557604, {expected}'
    assert len(result) <= 128


def test_unknown_tier_is_not_mislabeled_basic():
    with pytest.raises(ValueError):
        receipt_item_name('123', SimpleNamespace(access_tier='unknown'), 'subscription')


@pytest.mark.parametrize('tier,purpose,title', [
    ('basic', 'subscription', 'Подписка Basic'),
    ('mobile', 'subscription', 'Подписка Pro'),
    ('basic', 'gift', 'Подарочная подписка Basic'),
    ('mobile', 'gift', 'Подарочная подписка Pro'),
])
@pytest.mark.parametrize('days,term', [(7,'7 дней'), (30,'1 месяц'), (90,'3 месяца'), (180,'6 месяцев'), (365,'12 месяцев')])
def test_checkout_descriptions(tier,purpose,title,days,term):
    from app.services.payment_receipt import checkout_description
    plan=SimpleNamespace(access_tier=tier, duration_days=days)
    assert checkout_description(plan,purpose) == f'{title} - {term}'

@pytest.mark.parametrize('count',[1,2,3])
def test_device_checkout_descriptions(count):
    from app.services.payment_receipt import checkout_description
    plan=SimpleNamespace(access_tier='device_slots',code=f'device_slots_{count}')
    assert checkout_description(plan,'subscription') == f'Покупка дополнительного устройства - {count}'
