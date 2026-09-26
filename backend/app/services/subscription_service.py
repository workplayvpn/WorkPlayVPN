from datetime import UTC, datetime, timedelta
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.models.vpn_device import VpnDevice
from app.models.vpn_node import VpnNode
from app.services.mobile_profile_service import require_mobile_profile
from app.services.entitlements import active_entitlements
from app.services.xray_node import xray_node_service


class SubscriptionService:

    def get_active_subscription(
        self,
        database: Session,
        user_id: int,
        access_tier: str | None = None,
    ) -> Subscription | None:
        entitlements = active_entitlements(database, user_id)
        if access_tier is not None:
            entry = entitlements.get(access_tier)
            return entry[0] if entry else None
        return next((entry[0] for entry in entitlements.values()), None)

    def expire_stale_subscriptions(self, database: Session, user_id: int) -> bool:
        """Revoke expired access before handling a new device request."""
        now = datetime.now(UTC)
        stale = list(database.scalars(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                Subscription.expires_at.is_not(None),
                Subscription.expires_at <= now,
            ).order_by(Subscription.expires_at, Subscription.id)
        ).all())
        for subscription in stale:
            self.expire_subscription(database, subscription)
        return bool(stale)

    def expire_subscription(
        self,
        database: Session,
        subscription: Subscription,
    ) -> Subscription:
        if subscription.status != "active":
            return subscription

        # Serialize expiry with purchases and device creation for this user.
        database.scalar(
            select(User).where(User.id == subscription.user_id).with_for_update()
        )
        subscription = database.scalar(
            select(Subscription)
            .where(Subscription.id == subscription.id)
            .with_for_update()
        )
        if subscription is None or subscription.status != "active":
            return subscription

        plan = database.get(Plan, subscription.plan_id)
        if plan is None:
            raise HTTPException(status_code=500, detail="Subscription plan not found")
        remaining = active_entitlements(
            database, subscription.user_id,
            exclude_subscription_id=subscription.id,
        )
        other_tier = "mobile" if plan.access_tier == "basic" else "basic"
        other_live = other_tier in remaining
        same_tier_live = plan.access_tier in remaining

        # Mobile Wi-Fi and Basic share Direct. Basic expiry leaves both Xray
        # credentials intact while Mobile is live; Mobile expiry removes only
        # CDN while Basic is live. The last expiry removes both.
        action = (
            "none" if same_tier_live or (plan.access_tier == "basic" and other_live)
            else "mobile" if plan.access_tier == "mobile" and other_live
            else "all"
        )
        devices = list(database.scalars(
            select(VpnDevice).where(
                VpnDevice.user_id == subscription.user_id,
                VpnDevice.is_active.is_(True),
            )
        ).all())
        revoked: list[tuple[VpnDevice, VpnNode, str | None, str | None]] = []
        try:
            if action != "none":
                for device in devices:
                    node = database.get(VpnNode, device.node_id)
                    if node is None:
                        raise HTTPException(status_code=500, detail="VPN node not found")
                    if action == "mobile":
                        if device.mobile_xray_email:
                            xray_node_service.remove_mobile_user(
                                node=node, email=device.mobile_xray_email,
                            )
                            revoked.append((
                                device, node, device.mobile_xray_email,
                                device.mobile_xray_uuid,
                            ))
                            device.mobile_xray_email = None
                            device.mobile_xray_uuid = None
                    else:
                        xray_node_service.remove_device(node=node, device=device)
                        revoked.append((device, node, None, None))
            subscription.status = "expired"
            database.commit()
            database.refresh(subscription)
        except Exception as exc:
            database.rollback()
            for device, node, email, user_uuid in reversed(revoked):
                try:
                    if action == "mobile":
                        xray_node_service.add_mobile_user(
                            node=node, email=email, user_uuid=user_uuid,
                        )
                    else:
                        xray_node_service.add_device(node=node, device=device)
                except Exception:
                    pass
            if isinstance(exc, HTTPException):
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
        if subscription.status in {"applied", "active"}:
            plan = database.get(Plan, subscription.plan_id)
            current = self.get_active_subscription(
                database, subscription.user_id,
                plan.access_tier if plan else None,
            )
            return current or subscription
        if subscription.status != "pending":
            raise HTTPException(status_code=409, detail="Subscription cannot be activated")

        user = database.scalar(
            select(User).where(User.id == subscription.user_id).with_for_update()
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        subscription = database.scalar(
            select(Subscription)
            .where(Subscription.id == subscription.id)
            .with_for_update()
        )
        if subscription is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if subscription.status in {"applied", "active"}:
            plan = database.get(Plan, subscription.plan_id)
            current = self.get_active_subscription(
                database, user.id, plan.access_tier if plan else None,
            )
            return current or subscription
        if subscription.status != "pending":
            raise HTTPException(status_code=409, detail="Subscription cannot be activated")

        plan = database.get(Plan, subscription.plan_id)
        if plan is None:
            raise HTTPException(status_code=500, detail="Subscription plan not found")
        now = datetime.now(UTC)
        stale = list(database.scalars(select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
            Subscription.expires_at.is_not(None),
            Subscription.expires_at <= now,
        )).all())
        for old in stale:
            self.expire_subscription(database, old)
        if stale:
            # expire_subscription commits; take the user lock again before
            # provisioning the paid purchase.
            user = database.scalar(
                select(User).where(User.id == user.id).with_for_update()
            )
            subscription = database.scalar(
                select(Subscription)
                .where(Subscription.id == subscription.id).with_for_update()
            )
            if subscription.status != "pending":
                current = self.get_active_subscription(
                    database, user.id, plan.access_tier,
                )
                return current or subscription
        entitlements = active_entitlements(database, user.id, now=now)
        current_entry = entitlements.get(plan.access_tier)
        current = current_entry[0] if current_entry else None
        trial_to_mobile = False
        if current is None and plan.access_tier == "mobile":
            basic_entry = entitlements.get("basic")
            if basic_entry and basic_entry[1].code == "trial_1d":
                current = basic_entry[0]
                trial_to_mobile = True

        if current is not None:
            current_expires = current.expires_at
            if current_expires is not None and current_expires.tzinfo is None:
                current_expires = current_expires.replace(tzinfo=UTC)
            extension_start = max(current_expires or now, now)
            extension_end = extension_start + timedelta(days=plan.duration_days)
            added_mobile: list[tuple[VpnNode, str]] = []
            try:
                if trial_to_mobile:
                    for device in database.scalars(select(VpnDevice).where(
                        VpnDevice.user_id == user.id,
                        VpnDevice.is_active.is_(True),
                    )).all():
                        node = database.get(VpnNode, device.node_id)
                        if node is None:
                            raise HTTPException(status_code=500, detail="VPN node not found")
                        require_mobile_profile(database, node.id)
                        if bool(device.mobile_xray_uuid) != bool(device.mobile_xray_email):
                            raise HTTPException(status_code=409, detail="Incomplete Mobile credential")
                        if not device.mobile_xray_uuid:
                            device.mobile_xray_uuid = str(uuid.uuid4())
                            device.mobile_xray_email = f"mobile_{uuid.uuid4().hex}@workplayvpn"
                        xray_node_service.add_mobile_user(
                            node=node, email=device.mobile_xray_email,
                            user_uuid=device.mobile_xray_uuid,
                        )
                        added_mobile.append((node, device.mobile_xray_email))
                current.expires_at = extension_end
                current.plan_id = plan.id
                subscription.status = "applied"
                subscription.starts_at = extension_start
                subscription.expires_at = extension_end
                database.commit()
                database.refresh(current)
            except Exception:
                database.rollback()
                for node, email in reversed(added_mobile):
                    try:
                        xray_node_service.remove_mobile_user(node=node, email=email)
                    except Exception:
                        pass
                raise
            return current

        # A purchase of the other product starts its own clock. The device
        # list and Direct credential remain shared. Only CDN provisioning is
        # needed when Mobile is added to an existing Basic subscription.
        other_tier = "mobile" if plan.access_tier == "basic" else "basic"
        other_live = other_tier in entitlements
        devices = list(database.scalars(select(VpnDevice).where(
            VpnDevice.user_id == user.id,
            VpnDevice.is_active.is_(True),
        )).all())
        added_mobile: list[tuple[VpnNode, str]] = []
        restored_devices: list[tuple[VpnDevice, VpnNode]] = []
        try:
            if plan.access_tier == "mobile":
                for device in devices:
                    node = database.get(VpnNode, device.node_id)
                    if node is None:
                        raise HTTPException(status_code=500, detail="VPN node not found")
                    require_mobile_profile(database, node.id)
                    if bool(device.mobile_xray_uuid) != bool(device.mobile_xray_email):
                        raise HTTPException(status_code=409, detail="Incomplete Mobile credential")
                    if not device.mobile_xray_uuid:
                        device.mobile_xray_uuid = str(uuid.uuid4())
                        device.mobile_xray_email = f"mobile_{uuid.uuid4().hex}@workplayvpn"
                    if other_live:
                        xray_node_service.add_mobile_user(
                            node=node, email=device.mobile_xray_email,
                            user_uuid=device.mobile_xray_uuid,
                        )
                        added_mobile.append((node, device.mobile_xray_email))
            elif not other_live:
                for device in devices:
                    device.mobile_xray_uuid = None
                    device.mobile_xray_email = None
            if not other_live:
                restored_devices = self.restore_user_access(database, user.id)
            subscription.status = "active"
            subscription.starts_at = now
            subscription.expires_at = now + timedelta(days=plan.duration_days)
            database.commit()
            database.refresh(subscription)
        except Exception:
            database.rollback()
            for node, email in reversed(added_mobile):
                try:
                    xray_node_service.remove_mobile_user(node=node, email=email)
                except Exception:
                    pass
            for device, node in reversed(restored_devices):
                try:
                    xray_node_service.remove_device(node=node, device=device)
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

                xray_node_service.add_device(node=node, device=device)

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
                    xray_node_service.remove_device(
                        node=restored_node, device=restored_device,
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
