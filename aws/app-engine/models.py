from datetime import datetime
from config import db, ma

class Setting(db.Model):
    __tablename__ = "setting"
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer)
    type = db.Column(db.String(32))
    frame_rate = db.Column(db.String(32))
    refresh_rate = db.Column(db.String(32))
    dashboard_refresh_rate = db.Column(db.String(32))
    gauge_display = db.Column(db.String(32))
    updated = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
class SettingSchema(ma.ModelSchema):
    class Meta:
        model = Setting
        sqla_session = db.session
###
class Reading(db.Model):
    __tablename__ = "reading"
    id = db.Column(db.Integer, primary_key=True)
    id_device = db.Column(db.Integer)
    prediction = db.Column(db.String(64))
    accuracy = db.Column(db.String(64))
    alert = db.Column(db.Boolean)
    body = db.Column(db.String(128))
    timestamp = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
class ReadingSchema(ma.ModelSchema):
    class Meta:
        model = Reading
        sqla_session = db.session

###
class Device(db.Model):
    __tablename__ = "device"
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer)
    name = db.Column(db.String(32))
    image = db.Column(db.String(32))
    bucket = db.Column(db.String(32))
    type = db.Column(db.String(32))
    location = db.Column(db.String(32))
    prediction = db.Column(db.String(32))
    frame_rate = db.Column(db.String(32))
    refresh_rate = db.Column(db.String(32))
    notes = db.Column(db.String(64))
    high_threshold = db.Column(db.Float)
    low_threshold = db.Column(db.Float)
    maximum = db.Column(db.Integer)
    minimum = db.Column(db.Integer)
    units = db.Column(db.String(32))
    updated = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
class DeviceSchema(ma.ModelSchema):
    class Meta:
        model = Device
        sqla_session = db.session
###
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(32))
    password = db.Column(db.LargeBinary())
    display_name = db.Column(db.String(32))
    cell_number = db.Column(db.String(32))
    company = db.Column(db.String(32))
    thumbnail = db.Column(db.String(32))
    admin = db.Column(db.Boolean)
    updated = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
class UserSchema(ma.ModelSchema):
    class Meta:
        model = User
        sqla_session = db.session
###
class Notification(db.Model):
    __tablename__ = "notification"
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer)
    id_device = db.Column(db.Integer)
    text = db.Column(db.String(160))
    updated = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
class NotificationSchema(ma.ModelSchema):
    class Meta:
        model = Notification
        sqla_session = db.session
