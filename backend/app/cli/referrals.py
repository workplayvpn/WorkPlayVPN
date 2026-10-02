"""Manual payout queue. This command NEVER sends money or initiates a bank transfer."""
import argparse
import json
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.referral import ReferralWithdrawal
from app.models.user import User
from app.services import referrals

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("list")
    change=sub.add_parser("withdrawal");change.add_argument("id");change.add_argument("action",choices=("processing","paid","rejected"));change.add_argument("--reference");change.add_argument("--note")
    refund=sub.add_parser("refund");refund.add_argument("payment_id",type=int);refund.add_argument("--total-rub",required=True,help="Cumulative CONFIRMED refunded amount; does not refund the customer itself")
    args=p.parse_args()
    with SessionLocal() as db:
        try:
            if args.command=="list":
                rows=db.execute(select(ReferralWithdrawal,User.telegram_id).join(User,User.id==ReferralWithdrawal.user_id).where(ReferralWithdrawal.status.in_(referrals.OPEN)).order_by(ReferralWithdrawal.created_at)).all()
                print(json.dumps([dict(id=w.id,telegram_id=t,amount_rub=str(Decimal(w.amount_kopecks)/100),status=w.status) for w,t in rows],ensure_ascii=False));return
            if args.command=="withdrawal":
                if args.note and len(args.note)>300: p.error("Note exceeds 300 characters")
                item=referrals.process_withdrawal(db,args.id,args.action,args.reference,args.note)
                db.commit();print(json.dumps(dict(id=item.id,status=item.status)));return
            total=referrals.kopecks(args.total_rub)
            if total<0: p.error("Refund must not be negative")
            referrals.reverse_refund(db,args.payment_id,total);db.commit();print("REFERRAL_REFUND_ADJUSTED")
        except HTTPException as exc:
            db.rollback();p.exit(1,f"{exc.detail}\n")

if __name__=="__main__":main()
