import sqlite3
import bcrypt
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, or_, desc
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship
import config

Base = declarative_base()

# --- MODELS ---
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default='User')
    scope = Column(String, default='Read Only')

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    user_name = Column(String, nullable=False)
    assignee = Column(String)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    asset = relationship("Asset", back_populates="transactions")

class Asset(Base):
    __tablename__ = 'assets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String)
    make = Column(String)
    model = Column(String)
    serial_number = Column(String, unique=True, nullable=False)
    stock_number = Column(String)
    itec_account = Column(String)
    aqs_price = Column(Float)
    building = Column(String, nullable=False)
    room = Column(String, nullable=False)
    classification = Column(String)
    rack = Column(String)
    row = Column(String)
    table_num = Column(String)
    assigned_to = Column(String)
    tags = Column(String)
    date_added = Column(String)
    last_modified = Column(String)
    last_scanned = Column(String)
    
    transactions = relationship("Transaction", order_by=Transaction.id, back_populates="asset")

    def to_dict(self):
        return {
            "ID": self.id,
            "Type": self.device_type,
            "Make": self.make,
            "Model": self.model,
            "Serial": self.serial_number,
            "Stock": self.stock_number,
            "ITEC": self.itec_account,
            "Price": self.aqs_price,
            "Building": self.building,
            "Room": self.room,
            "Rack": self.rack,
            "Row": self.row,
            "Table": self.table_num,
            "Assigned To": self.assigned_to,
            "Tags": self.tags,
            "Date Added": self.date_added,
            "Last Modified": self.last_modified,
            "Last Scanned": self.last_scanned
        }

# --- CONTROLLER ---
class Database:
    def __init__(self):
        self.engine = create_engine(f'sqlite:///{config.DB_NAME}', connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        self.create_default_admin()

    def get_session(self):
        return self.Session()

    def create_default_admin(self):
        session = self.get_session()
        if session.query(User).count() == 0:
            pw_bytes = "admin123".encode('utf-8')
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(pw_bytes, salt).decode('utf-8')
            
            admin = User(username="admin", password_hash=hashed, role="Admin", scope=config.SCOPE_ADMIN)
            session.add(admin)
            session.commit()
        session.close()

    # --- USER AUTH ---
    def verify_user(self, username, password):
        session = self.get_session()
        user = session.query(User).filter_by(username=username).first()
        session.close()
        
        if user:
            if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                return (user.id, user.username, user.role, user.scope)
        return None

    def add_user(self, username, password, role="User", scope="Read Only"):
        session = self.get_session()
        if session.query(User).filter_by(username=username).first():
            session.close()
            return False
        
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        new_user = User(username=username, password_hash=hashed, role=role, scope=scope)
        session.add(new_user)
        session.commit()
        session.close()
        return True

    def get_all_users(self):
        session = self.get_session()
        users = session.query(User).all()
        result = [(u.id, u.username, u.role, u.scope) for u in users]
        session.close()
        return result
        
    def delete_user(self, user_id):
        session = self.get_session()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            session.delete(user)
            session.commit()
        session.close()

    def update_user_scope(self, user_id, new_scope):
        session = self.get_session()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.scope = new_scope
            session.commit()
        session.close()

    def update_user_password(self, user_id, new_password):
        session = self.get_session()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            salt = bcrypt.gensalt()
            user.password_hash = bcrypt.hashpw(new_password.encode(), salt).decode('utf-8')
            session.commit()
        session.close()

    # --- ASSETS ---
    def add_asset(self, data):
        session = self.get_session()
        try:
            asset = Asset(
                device_type=data[0], make=data[1], model=data[2], serial_number=data[3],
                stock_number=data[4], itec_account=data[5], aqs_price=data[6],
                building=data[7], room=data[8], classification=data[9],
                rack=data[10], row=data[11], table_num=data[12], assigned_to=data[13],
                tags=data[14], date_added=data[15], last_modified=data[16], last_scanned=data[17]
            )
            session.add(asset)
            session.commit()
            return asset.id
        except Exception as e:
            print(e)
            session.rollback()
            return None
        finally:
            session.close()

    def get_all_assets(self, tag_filter=None, search_query=None, limit=None, offset=0):
        session = self.get_session()
        query = session.query(Asset)

        if tag_filter and tag_filter != "All":
            query = query.filter(Asset.tags.like(f"%{tag_filter}%"))

        if search_query:
            terms = search_query.split()
            for term in terms:
                term_filter = f"%{term}%"
                query = query.filter(or_(
                    Asset.make.ilike(term_filter),
                    Asset.model.ilike(term_filter),
                    Asset.serial_number.ilike(term_filter),
                    Asset.device_type.ilike(term_filter),
                    Asset.assigned_to.ilike(term_filter)
                ))

        total_count = query.count()
        query = query.order_by(Asset.id.desc())
        
        if limit:
            query = query.limit(limit).offset(offset)
            
        assets = query.all()
        results = [a.to_dict() for a in assets]
        session.close()
        return results, total_count

    def get_asset_by_serial(self, serial):
        session = self.get_session()
        asset = session.query(Asset).filter_by(serial_number=serial).first()
        result = asset.to_dict() if asset else None
        session.close()
        return result
    
    def get_asset_by_id(self, asset_id):
        session = self.get_session()
        asset = session.query(Asset).filter_by(id=asset_id).first()
        result = asset.to_dict() if asset else None
        session.close()
        return result

    def update_scan_time(self, serial):
        session = self.get_session()
        asset = session.query(Asset).filter_by(serial_number=serial).first()
        if asset:
            asset.last_scanned = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session.commit()
        session.close()

    def update_asset_dict(self, asset_id, data_dict):
        # FIX IMPLEMENTED: Mapping UI headers to DB columns
        UI_TO_MODEL_MAP = {
            "Type": "device_type",
            "Make": "make",
            "Model": "model",
            "Serial": "serial_number",
            "Stock": "stock_number",
            "ITEC": "itec_account",
            "Price": "aqs_price",
            "Building": "building",
            "Room": "room",
            "Rack": "rack",
            "Row": "row",
            "Table": "table_num",
            "Assigned To": "assigned_to",
            "Tags": "tags",
            "Last Scanned": "last_scanned"
        }

        session = self.get_session()
        asset = session.query(Asset).filter_by(id=asset_id).first()
        if asset:
            try:
                for ui_key, value in data_dict.items():
                    if ui_key in UI_TO_MODEL_MAP:
                        db_key = UI_TO_MODEL_MAP[ui_key]
                        setattr(asset, db_key, value)
                
                asset.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                session.commit()
                return True
            except Exception as e:
                print(f"Update failed: {e}")
                session.rollback()
                return False
            finally:
                session.close()
        return False
        
    def delete_asset(self, asset_id):
        session = self.get_session()
        asset = session.query(Asset).filter_by(id=asset_id).first()
        if asset:
            session.delete(asset)
            session.commit()
        session.close()

    def add_transaction(self, asset_id, user_name, action, assignee=None):
        session = self.get_session()
        try:
            trans = Transaction(asset_id=asset_id, user_name=user_name, action=action, assignee=assignee, timestamp=datetime.now())
            session.add(trans)
            asset = session.query(Asset).filter_by(id=asset_id).first()
            if asset:
                if action == "CHECKOUT": asset.assigned_to = assignee
                elif action == "CHECKIN": asset.assigned_to = "Available"
                asset.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def get_all_transactions(self):
        session = self.get_session()
        transactions = session.query(Transaction).join(Asset).order_by(Transaction.timestamp.desc()).limit(500).all()
        logs = []
        for t in transactions:
            logs.append({
                "Timestamp": t.timestamp, "Action": t.action, "User": t.user_name,
                "Asset Serial": t.asset.serial_number, "Asset Model": f"{t.asset.make} {t.asset.model}",
                "Assignee": t.assignee
            })
        session.close()
        return logs

    def get_stats(self):
        session = self.get_session()
        total = session.query(Asset).count()
        val_res = session.query(Asset.aqs_price).all()
        value = sum(r[0] for r in val_res if r[0])
        types = session.query(Asset.device_type).distinct().count()
        tags_res = session.query(Asset.tags).filter(Asset.tags != None).all()
        unique_tags = set()
        for row in tags_res:
            if row[0]: unique_tags.update([t.strip() for t in row[0].split(',')])
        type_res = session.query(Asset.device_type).distinct().all()
        
        session.close()
        return total, value, types, sorted(list(unique_tags)), [r[0] for r in type_res if r[0]]