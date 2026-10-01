from app.services.catalog import available_plans
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.device_activations import build_activation_url
from app.api.happ_auto_route import auto_route_allowed
from app.api.telegram_webapp_auth import (
    require_telegram_webapp_auth,
)
from app.core.config import settings
from app.db.dependencies import get_db
from app.models.location import Location
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.schemas.mini_app import (
    MiniAppPaymentCreate,
    MiniAppPaymentRead,
    MiniAppActivationCreate,
    MiniAppActivationRead,
    MiniAppDeviceCreate,
    MiniAppDeviceCreateRead,
    MiniAppDeviceRead,
    MiniAppCatalogRead,
    MiniAppLocationRead,
    MiniAppPlanRead,
    MiniAppRegionRead,
    MiniAppRegionUpdate,
    MiniAppDeviceSummaryRead,
    MiniAppMeRead,
    MiniAppSubscriptionRead,
    MiniAppUserRead,
)
from app.services.device_activation_service import device_activation_service
from app.services.payment_service import payment_service
from app.services.subscription_service import subscription_service
from app.services.entitlements import active_entitlements, shared_device_limit
from app.services.subscription_token_service import (
    subscription_token_service,
)
from app.services.vpn_device_service import vpn_device_service
from app.services.payment_redirect_service import (
    payment_redirect_service,
)
from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthResult,
)


router = APIRouter(
    prefix="/mini-app",
    tags=["mini-app"],
)


def get_user_region(
    *,
    database: Session,
    user: User,
) -> Location | None:
    if user.preferred_location_id is not None:
        preferred_location = database.scalar(
            select(Location)
            .join(
                VpnNode,
                VpnNode.location_id == Location.id,
            )
            .where(
                Location.id == user.preferred_location_id,
                Location.is_active.is_(True),
                VpnNode.is_active.is_(True),
            )
            .order_by(VpnNode.id.asc())
        )

        if preferred_location is not None:
            return preferred_location

    device_location = database.scalar(
        select(Location)
        .join(VpnNode, VpnNode.location_id == Location.id)
        .join(VpnDevice, VpnDevice.node_id == VpnNode.id)
        .where(
            VpnDevice.user_id == user.id,
            VpnDevice.is_active.is_(True),
            Location.is_active.is_(True),
            VpnNode.is_active.is_(True),
        )
        .order_by(
            VpnDevice.created_at.asc(),
            VpnDevice.id.asc(),
        )
    )

    if device_location is not None:
        return device_location

    return database.scalar(
        select(Location)
        .join(VpnNode, VpnNode.location_id == Location.id)
        .where(
            Location.is_active.is_(True),
            VpnNode.is_active.is_(True),
        )
        .order_by(VpnNode.id.asc())
    )


def get_visible_subscription(database: Session, user: User) -> Subscription | None:
    entitlements = active_entitlements(database, user.id)
    for tier in ("basic", "mobile"):
        if tier in entitlements:
            return entitlements[tier][0]
    return database.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == "pending",
        ).order_by(Subscription.created_at.desc())
    )


@router.get(
    "/me",
    response_model=MiniAppMeRead,
)
def get_me(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppMeRead:
    telegram_user = auth.user

    upsert_user = (
        insert(User)
        .values(
            telegram_id=telegram_user.id,
            first_name=telegram_user.first_name,
            username=telegram_user.username,
        )
        .on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "first_name": telegram_user.first_name,
                "username": telegram_user.username,
            },
        )
    )

    database.execute(upsert_user)
    database.commit()

    user = database.scalar(
        select(User).where(
            User.telegram_id == telegram_user.id
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mini App user synchronization failed",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    entitlements = active_entitlements(database, user.id)
    subscription = get_visible_subscription(database=database, user=user)
    subscriptions_read = [
        MiniAppSubscriptionRead(
            status=item.status, plan_code=plan.code,
            plan_name=plan.name, starts_at=item.starts_at,
            expires_at=item.expires_at, access_tier=tier,
        )
        for tier, (item, plan) in entitlements.items()
    ]
    subscription_read: MiniAppSubscriptionRead | None = None
    if subscriptions_read:
        subscription_read = next(
            (entry for entry in subscriptions_read if entry.access_tier == "basic"),
            subscriptions_read[0],
        )
    elif subscription is not None:
        plan = database.get(Plan, subscription.plan_id)
        if plan is None:
            raise HTTPException(status_code=500, detail="Subscription plan not found")
        subscription_read = MiniAppSubscriptionRead(
            status=subscription.status, plan_code=plan.code,
            plan_name=plan.name, starts_at=subscription.starts_at,
            expires_at=subscription.expires_at, access_tier=plan.access_tier,
        )
    total_device_limit = shared_device_limit(entitlements, user.extra_device_slots)
    connect_urls: dict[str, str] = {}
    auto_connect_urls: dict[str, str] = {}
    basic_device_connect_urls: dict[str, str] = {}
    if entitlements:
        token_record, basic_token = subscription_token_service.get_or_create_token(
            database=database, telegram_id=user.telegram_id,
        )
        for tier in entitlements:
            raw = (basic_token if tier == "basic" else
                   subscription_token_service.scoped_token(token_record, tier))
            connect_urls[tier] = f"{settings.connect_base_url.rstrip('/')}/{raw}"
            if tier == "basic":
                basic_devices = database.scalars(
                    select(VpnDevice).where(
                        VpnDevice.user_id == user.id,
                        VpnDevice.is_active.is_(True),
                    ).order_by(VpnDevice.id.asc())
                ).all()
                for device in basic_devices:
                    basic_device_connect_urls[str(device.id)] = (
                        f"{settings.connect_base_url.rstrip('/')}/device/"
                        f"{device.id}/{raw}"
                    )
                if basic_device_connect_urls:
                    connect_urls["basic"] = next(iter(basic_device_connect_urls.values()))
            if tier == "mobile" and auto_route_allowed(user.id):
                ready_devices = database.scalars(
                    select(VpnDevice).where(
                        VpnDevice.user_id == user.id,
                        VpnDevice.is_active.is_(True),
                    ).order_by(VpnDevice.id.asc())
                ).all()
                for device in ready_devices:
                    if device.mobile_xray_uuid and device.mobile_xray_email:
                        auto_connect_urls[str(device.id)] = (
                            f"{settings.connect_base_url.rstrip('/')}/auto/routed/device/"
                            f"{device.id}/{raw}"
                        )
                if auto_connect_urls:
                    connect_urls["mobile"] = next(iter(auto_connect_urls.values()))

    active_device_count = database.scalar(
        select(func.count(VpnDevice.id)).where(
            VpnDevice.user_id == user.id,
            VpnDevice.is_active.is_(True),
        )
    )

    trial_was_used = database.scalar(
        select(Subscription.id)
        .join(
            Plan,
            Subscription.plan_id == Plan.id,
        )
        .where(
            Subscription.user_id == user.id,
            Plan.code == "trial_1d",
        )
        .limit(1)
    )

    current_region = get_user_region(
        database=database,
        user=user,
    )

    return MiniAppMeRead(
        user=MiniAppUserRead(
            telegram_id=user.telegram_id,
            first_name=user.first_name
            or telegram_user.first_name,
            username=user.username,
        ),
        subscription=subscription_read,
        subscriptions=subscriptions_read,
        connect_urls=connect_urls,
        auto_connect_urls=auto_connect_urls,
        basic_device_connect_urls=basic_device_connect_urls,
        devices=MiniAppDeviceSummaryRead(
            active_count=active_device_count or 0,
            total_limit=total_device_limit,
        ),
        current_region=(
            MiniAppRegionRead(
                code=current_region.code,
                name=current_region.name,
            )
            if current_region is not None
            else None
        ),
        trial_available=(
            trial_was_used is None
            and not entitlements
        ),
    )


@router.patch(
    "/region",
    response_model=MiniAppRegionRead,
)
def change_region(
    payload: MiniAppRegionUpdate,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppRegionRead:
    location = vpn_device_service.change_account_location(
        database=database,
        telegram_id=auth.user.id,
        location_code=payload.location_code,
    )

    return MiniAppRegionRead(
        code=location.code,
        name=location.name,
    )


@router.get(
    "/catalog",
    response_model=MiniAppCatalogRead,
)
def get_catalog(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppCatalogRead:
    plans = available_plans(database, auth.user.id)

    locations = database.scalars(
        select(Location)
        .where(Location.is_active.is_(True))
        .order_by(Location.name)
    ).all()

    available_location_ids = set(
        database.scalars(
            select(VpnNode.location_id).where(
                VpnNode.is_active.is_(True)
            )
        ).all()
    )

    return MiniAppCatalogRead(
        plans=[
            MiniAppPlanRead(
                code=plan.code,
                name=plan.name,
                duration_days=plan.duration_days,
                price_amount=plan.price_amount,
                currency=plan.currency,
                device_limit=plan.device_limit,
                access_tier=plan.access_tier,
            )
            for plan in plans
        ],
        locations=[
            MiniAppLocationRead(
                code=location.code,
                name=location.name,
                available=(
                    location.id in available_location_ids
                ),
            )
            for location in locations
        ],
    )


@router.post(
    "/trial",
    response_model=MiniAppSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
def start_trial(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppSubscriptionRead:
    user = database.scalar(
        select(User).where(
            User.telegram_id == auth.user.id
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mini App user not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    subscription = subscription_service.create_trial(
        database=database,
        user_id=user.id,
    )

    plan = database.get(
        Plan,
        subscription.plan_id,
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trial plan not found",
        )

    return MiniAppSubscriptionRead(
        status=subscription.status,
        plan_code=plan.code,
        plan_name=plan.name,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
    )


def build_mini_app_device(
    *,
    database: Session,
    device: VpnDevice,
) -> MiniAppDeviceRead:
    node = database.get(
        VpnNode,
        device.node_id,
    )

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VPN node not found",
        )

    return MiniAppDeviceRead(
        id=device.id,
        public_id=device.public_id,
        happ_device_model=device.happ_device_model,
        happ_device_os=device.happ_device_os,
        device_name=device.device_name,
        node_code=node.code,
        node_name=node.name.replace("WorkPlayVPN", "Work&PlayVPN"),
        is_active=device.is_active,
        created_at=device.created_at,
    )


@router.get(
    "/devices",
    response_model=list[MiniAppDeviceRead],
)
def get_devices(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[MiniAppDeviceRead]:
    devices = vpn_device_service.get_devices(
        database=database,
        telegram_id=auth.user.id,
    )

    return [
        build_mini_app_device(
            database=database,
            device=device,
        )
        for device in devices
    ]


@router.post(
    "/devices",
    response_model=MiniAppDeviceCreateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_device(
    payload: MiniAppDeviceCreate,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppDeviceCreateRead:
    device_name = payload.device_name.strip()

    if not device_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Device name required",
        )

    user = database.scalar(
        select(User).where(
            User.telegram_id == auth.user.id,
            User.is_active.is_(True),
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    location = get_user_region(
        database=database,
        user=user,
    )

    node = (
        database.scalar(
            select(VpnNode)
            .where(
                VpnNode.location_id == location.id,
                VpnNode.is_active.is_(True),
            )
            .order_by(VpnNode.id.asc())
        )
        if location is not None
        else None
    )

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VPN node unavailable",
        )

    device = vpn_device_service.create_device(
        database=database,
        telegram_id=auth.user.id,
        node_code=node.code,
        device_name=device_name,
        client_instance_id=payload.client_instance_id,
    )

    if user.preferred_location_id != location.id:
        user.preferred_location_id = location.id
        database.commit()

    token_record, basic_token = subscription_token_service.get_or_create_token(
        database=database, telegram_id=auth.user.id,
    )
    entitlements = active_entitlements(database, user.id)
    mobile_token = (
        subscription_token_service.scoped_token(token_record, "mobile")
        if "mobile" in entitlements else None
    )
    mobile_url = (
        f"{settings.connect_base_url.rstrip('/')}/auto/routed/device/"
        f"{device.id}/{mobile_token}"
        if mobile_token and auto_route_allowed(user.id)
        and device.mobile_xray_uuid and device.mobile_xray_email
        else f"{settings.connect_base_url.rstrip('/')}/{mobile_token}"
        if mobile_token else None
    )
    connect_url = (
        f"{settings.connect_base_url.rstrip('/')}/device/{device.id}/{basic_token}"
        if "basic" in entitlements else mobile_url
    )

    device_read = build_mini_app_device(
        database=database,
        device=device,
    )

    return MiniAppDeviceCreateRead(
        **device_read.model_dump(),
        connect_url=connect_url,
        mobile_connect_url=mobile_url,
    )





@router.post(
    "/device-activations",
    response_model=MiniAppActivationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_device_activation(
    payload: MiniAppActivationCreate,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppActivationRead:
    activation, raw_token = (
        device_activation_service.create_activation(
            database=database,
            telegram_id=auth.user.id,
            location_code=payload.location_code.upper(),
        )
    )

    return MiniAppActivationRead(
        activation_id=activation.id,
        expires_at=activation.expires_at,
        activation_url=build_activation_url(raw_token),
    )


@router.delete(
    "/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_device(
    device_id: int,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> Response:
    vpn_device_service.remove_device(
        database=database,
        telegram_id=auth.user.id,
        device_id=device_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.post(
    "/payments",
    response_model=MiniAppPaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: MiniAppPaymentCreate,
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppPaymentRead:
    payment = payment_service.create_payment(
        database=database,
        telegram_id=auth.user.id,
        plan_code=payload.plan_code,
        provider=settings.payment_default_provider,
        idempotency_key=payload.idempotency_key,
    )

    return MiniAppPaymentRead(
        id=payment.id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        confirmation_url=(
            payment_redirect_service
            .build_public_confirmation_url(payment)
        ),
        created_at=payment.created_at,
        expires_at=payment.expires_at,
        paid_at=payment.paid_at,
    )


@router.get(
    "/payments/current",
    response_model=MiniAppPaymentRead | None,
)
def get_current_payment(
    auth: Annotated[
        TelegramWebAppAuthResult,
        Depends(require_telegram_webapp_auth),
    ],
    database: Annotated[
        Session,
        Depends(get_db),
    ],
) -> MiniAppPaymentRead | None:
    user = database.scalar(
        select(User).where(
            User.telegram_id == auth.user.id,
            User.is_active.is_(True),
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    payment = database.scalar(
        select(Payment)
        .where(
            Payment.user_id == user.id,
            Payment.status == "pending",
            or_(
                Payment.expires_at.is_(None),
                Payment.expires_at > datetime.now(UTC),
            ),
        )
        .order_by(Payment.created_at.desc())
    )

    if payment is None:
        return None

    return MiniAppPaymentRead(
        id=payment.id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        confirmation_url=(
            payment_redirect_service
            .build_public_confirmation_url(payment)
        ),
        created_at=payment.created_at,
        expires_at=payment.expires_at,
        paid_at=payment.paid_at,
    )
