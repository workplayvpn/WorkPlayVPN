from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.xray_node import xray_node_service


class SubscriptionService:

    def get_active_subscription(
        self,
        database: Session,
        user_id: int,
    ) -> Subscription | None:
        return database.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .order_by(
                Subscription.created_at.desc()
            )
        )

    def expire_subscription(
        self,
        database: Session,
        subscription: Subscription,
    ) -> Subscription:
        if subscription.status != "active":
            return subscription

        devices = list(
            database.scalars(
                select(VpnDevice).where(
                    VpnDevice.user_id == subscription.user_id,
                    VpnDevice.is_active.is_(True),
                )
            ).all()
        )

        revoked_devices: list[
            tuple[VpnDevice, VpnNode]
        ] = []

        try:
            for device in devices:
                node = database.get(
                    VpnNode,
                    device.node_id,
                )

                if node is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="VPN node not found",
                    )

                xray_node_service.remove_user(
                    node=node,
                    email=device.xray_email,
                )

                revoked_devices.append(
                    (
                        device,
                        node,
                    )
                )

            subscription.status = "expired"

            database.commit()
            database.refresh(subscription)

        except Exception as exc:
            database.rollback()

            for revoked_device, revoked_node in reversed(
                revoked_devices
            ):
                try:
                    xray_node_service.add_user(
                        node=revoked_node,
                        email=revoked_device.xray_email,
                        user_uuid=revoked_device.xray_uuid,
                    )
                except Exception:
                    pass

            if isinstance(
                exc,
                HTTPException,
            ):
                raise

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to expire subscription safely",
            ) from exc

        return subscription

    def expire_if_needed(
        self,
        database: Session,
        subscription: Subscription,
    ) -> Subscription:
        if subscription.status != "active":
            return subscription

        if subscription.expires_at is None:
            return subscription

        now = datetime.now(UTC)

        if subscription.expires_at <= now:
            return self.expire_subscription(
                database=database,
                subscription=subscription,
            )

        return subscription

    def activate_subscription(
        self,
        database: Session,
        subscription: Subscription,
    ) -> Subscription:
        # Повторное подтверждение уже активированной покупки
        # ничего дополнительно не начисляет.
        if subscription.status == "applied":
            current_subscription = (
                self.get_active_subscription(
                    database=database,
                    user_id=subscription.user_id,
                )
            )

            if current_subscription is not None:
                return current_subscription

            return subscription

        if subscription.status == "active":
            return subscription

        if subscription.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription cannot be activated",
            )

        # Блокируем конкретного пользователя.
        # Два одновременных платёжных webhook одного
        # пользователя не смогут продлить подписку параллельно.
        user = database.scalar(
            select(User)
            .where(
                User.id == subscription.user_id,
            )
            .with_for_update()
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        subscription = database.scalar(
            select(Subscription)
            .where(
                Subscription.id == subscription.id,
            )
            .with_for_update()
        )

        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found",
            )

        if subscription.status == "applied":
            current_subscription = (
                self.get_active_subscription(
                    database=database,
                    user_id=user.id,
                )
            )

            if current_subscription is not None:
                return current_subscription

            return subscription

        if subscription.status == "active":
            return subscription

        if subscription.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription cannot be activated",
            )

        plan = database.get(
            Plan,
            subscription.plan_id,
        )

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Subscription plan not found",
            )

        now = datetime.now(UTC)

        current_subscription = database.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
                Subscription.id != subscription.id,
            )
            .order_by(
                Subscription.created_at.desc()
            )
        )

        # -------------------------------------------------
        # СЦЕНАРИЙ 1:
        # У пользователя уже есть действующая подписка.
        # Просто добавляем купленный срок.
        # -------------------------------------------------

        if current_subscription is not None:
            if (
                current_subscription.expires_at is not None
                and current_subscription.expires_at > now
            ):
                extension_start = (
                    current_subscription.expires_at
                )
            else:
                extension_start = now

            extension_end = (
                extension_start
                + timedelta(
                    days=plan.duration_days
                )
            )

            current_subscription.expires_at = (
                extension_end
            )

            # Показываем последний купленный тариф.
            current_subscription.plan_id = plan.id

            subscription.status = "applied"
            subscription.starts_at = extension_start
            subscription.expires_at = extension_end

            try:
                database.commit()
                database.refresh(
                    current_subscription
                )
            except Exception:
                database.rollback()
                raise

            return current_subscription

        # -------------------------------------------------
        # СЦЕНАРИЙ 2:
        # Активной подписки нет.
        # Возвращаем существующие устройства в Xray
        # с теми же UUID и активируем покупку.
        # -------------------------------------------------

        restored_devices = (
            self.restore_user_access(
                database=database,
                user_id=user.id,
            )
        )

        subscription.status = "active"
        subscription.starts_at = now
        subscription.expires_at = (
            now
            + timedelta(
                days=plan.duration_days
            )
        )

        try:
            database.commit()
            database.refresh(subscription)

        except Exception:
            database.rollback()

            # Если PostgreSQL не смог сохранить ACTIVE,
            # возвращаем Xray в исходное состояние.
            for restored_device, restored_node in reversed(
                restored_devices
            ):
                try:
                    xray_node_service.remove_user(
                        node=restored_node,
                        email=restored_device.xray_email,
                    )
                except Exception:
                    pass

            raise

        return subscription

    def create_trial(
        self,
        database: Session,
        user_id: int,
    ) -> Subscription:
        user = database.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        )

        if user is None:
            database.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        plan = database.scalar(
            select(Plan).where(
                Plan.code == "trial_1d",
                Plan.is_active.is_(True),
            )
        )

        if plan is None:
            database.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Trial plan not found",
            )

        previous_trial = database.scalar(
            select(Subscription)
            .join(
                Plan,
                Subscription.plan_id == Plan.id,
            )
            .where(
                Subscription.user_id == user.id,
                Plan.code == "trial_1d",
            )
        )

        if previous_trial is not None:
            database.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Trial already used",
            )

        active_subscription = self.get_active_subscription(
            database=database,
            user_id=user.id,
        )

        if active_subscription is not None:
            database.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has active subscription",
            )

        now = datetime.now(UTC)
        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status="active",
            starts_at=now,
            expires_at=now + timedelta(days=plan.duration_days),
        )

        database.add(subscription)

        try:
            database.commit()
            database.refresh(subscription)
        except Exception:
            database.rollback()
            raise

        return subscription


    def restore_user_access(
        self,
        database: Session,
        user_id: int,
    ) -> list[tuple[VpnDevice, VpnNode]]:
        user = database.get(
            User,
            user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        devices = list(
            database.scalars(
                select(VpnDevice).where(
                    VpnDevice.user_id == user.id,
                    VpnDevice.is_active.is_(True),
                )
            ).all()
        )

        restored_devices: list[
            tuple[VpnDevice, VpnNode]
        ] = []

        try:
            for device in devices:
                node = database.get(
                    VpnNode,
                    device.node_id,
                )

                if node is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="VPN node not found",
                    )

                xray_node_service.add_user(
                    node=node,
                    email=device.xray_email,
                    user_uuid=device.xray_uuid,
                )

                restored_devices.append(
                    (
                        device,
                        node,
                    )
                )

        except Exception as exc:
            for restored_device, restored_node in reversed(
                restored_devices
            ):
                try:
                    xray_node_service.remove_user(
                        node=restored_node,
                        email=restored_device.xray_email,
                    )
                except Exception:
                    pass

            if isinstance(
                exc,
                HTTPException,
            ):
                raise

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="VPN node unavailable",
            ) from exc

        return restored_devices


subscription_service = SubscriptionService()