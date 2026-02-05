"""Add complete test data script"""
from datetime import date, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Board, Location, Transport, TransportCarrier

app = create_app()
with app.app_context():
    # 既存データを確認
    if User.query.count() == 0:
        # 管理者ユーザー
        admin = User(username="dev_admin", role="admin")
        admin.set_password("password")
        db.session.add(admin)
        
        # メンバーユーザー
        member = User(username="dev_member", role="member")
        member.set_password("password")
        db.session.add(member)
        
        # 追加メンバー
        member2 = User(username="田中太郎", role="member")
        member2.set_password("password")
        db.session.add(member2)
        
        member3 = User(username="鈴木花子", role="member")
        member3.set_password("password")
        db.session.add(member3)
        
        db.session.commit()
        print("Users added")
    
    if Location.query.count() == 0:
        # 拠点
        locations = [
            Location(name="横浜", is_base=True, display_order=1),
            Location(name="海の公園", is_base=True, display_order=2),
            Location(name="平塚", is_base=True, display_order=3),
            Location(name="日本橋", is_base=True, display_order=4),
        ]
        for loc in locations:
            db.session.add(loc)
        db.session.commit()
        print("Locations added")
    
    if Board.query.count() == 0:
        # ボード
        boards = [
            Board(name="SUP-01", location="横浜", user="dev_admin", updated_at="2026-02-06 10:00", serial_number="SN-001"),
            Board(name="SUP-02", location="横浜", user="dev_admin", updated_at="2026-02-06 10:00", serial_number="SN-002"),
            Board(name="SUP-03", location="海の公園", user="dev_member", updated_at="2026-02-05 15:00", serial_number="SN-003"),
            Board(name="SUP-04", location="平塚", user="田中太郎", updated_at="2026-02-04 12:00", serial_number="SN-004"),
            Board(name="SUP-05", location="日本橋", user="鈴木花子", updated_at="2026-02-03 09:00", serial_number="SN-005"),
            Board(name="SUP-06", location="横浜", user="dev_admin", updated_at="2026-02-06 10:00"),
            Board(name="SUP-07", location="海の公園", user="dev_member", updated_at="2026-02-05 14:00"),
            Board(name="SUP-08", location="平塚", user="田中太郎", updated_at="2026-02-04 11:00"),
        ]
        for board in boards:
            db.session.add(board)
        db.session.commit()
        print("Boards added")
    
    # 運搬データ
    if Transport.query.count() == 0:
        admin = User.query.filter_by(username="dev_admin").first()
        member = User.query.filter_by(username="dev_member").first()
        tanaka = User.query.filter_by(username="田中太郎").first()
        suzuki = User.query.filter_by(username="鈴木花子").first()
        
        today = date.today()
        
        # 運搬1: 予定済み（明日）
        t1 = Transport(
            board_id=1,
            status="scheduled",
            origin="横浜",
            destination="海の公園",
            current_location="横浜",
            reason_type=1,
            departure_date=today + timedelta(days=1),
            departure_timing="before_1",
            arrival_date=today + timedelta(days=1),
            arrival_timing="after_3",
            created_by_id=admin.id
        )
        db.session.add(t1)
        db.session.flush()
        
        c1 = TransportCarrier(
            transport_id=t1.id,
            sequence=1,
            user_id=admin.id,
            status="pending"
        )
        db.session.add(c1)
        
        # 運搬2: 進行中
        t2 = Transport(
            board_id=3,
            status="in_progress",
            origin="海の公園",
            destination="平塚",
            current_location="海の公園",
            reason_type=2,
            departure_date=today,
            departure_timing="before_1",
            arrival_date=today,
            arrival_timing="between_2_3",
            actual_departure=datetime.combine(today, datetime.min.time()).replace(hour=8, minute=30),
            created_by_id=member.id
        )
        db.session.add(t2)
        db.session.flush()
        
        c2 = TransportCarrier(
            transport_id=t2.id,
            sequence=1,
            user_id=member.id,
            status="active"
        )
        db.session.add(c2)
        
        # 運搬3: 目的地未定（3日前から）
        t3 = Transport(
            board_id=4,
            status="destination_pending",
            origin="平塚",
            destination=None,
            current_location="平塚",
            reason_type=3,
            departure_date=today - timedelta(days=3),
            departure_timing="after_3",
            created_by_id=tanaka.id
        )
        db.session.add(t3)
        db.session.flush()
        
        c3 = TransportCarrier(
            transport_id=t3.id,
            sequence=1,
            user_id=tanaka.id,
            status="pending"
        )
        db.session.add(c3)
        
        # 運搬4: 完了済み（昨日）
        yesterday = today - timedelta(days=1)
        t4 = Transport(
            board_id=5,
            status="completed",
            origin="海の公園",
            destination="日本橋",
            current_location="日本橋",
            reason_type=1,
            departure_date=yesterday,
            departure_timing="before_1",
            arrival_date=yesterday,
            arrival_timing="after_3",
            actual_departure=datetime.combine(yesterday, datetime.min.time()).replace(hour=8, minute=0),
            actual_arrival=datetime.combine(yesterday, datetime.min.time()).replace(hour=18, minute=0),
            created_by_id=suzuki.id
        )
        db.session.add(t4)
        db.session.flush()
        
        c4 = TransportCarrier(
            transport_id=t4.id,
            sequence=1,
            user_id=suzuki.id,
            status="completed"
        )
        db.session.add(c4)
        
        # 運搬5: 目的地未定（5日前から - 通知対象）
        t5 = Transport(
            board_id=6,
            status="destination_pending",
            origin="横浜",
            destination=None,
            current_location="横浜",
            reason_type=4,
            reason_detail="イベント用に移動予定",
            departure_date=today - timedelta(days=5),
            departure_timing="other",
            created_by_id=admin.id
        )
        db.session.add(t5)
        db.session.flush()
        
        c5 = TransportCarrier(
            transport_id=t5.id,
            sequence=1,
            user_id=admin.id,
            status="pending"
        )
        db.session.add(c5)
        
        db.session.commit()
        print("Transports and carriers added")
    
    print("Test data setup complete!")
    print(f"  Users: {User.query.count()}")
    print(f"  Locations: {Location.query.count()}")
    print(f"  Boards: {Board.query.count()}")
    print(f"  Transports: {Transport.query.count()}")
