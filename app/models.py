from app import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    height_cm = db.Column(db.Float)
    goal_weight = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)