from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    height_cm = db.Column(db.Float)
    goal_weight = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class WeightLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    weight_kg = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    notes = db.Column(db.String(200))
    
    user = db.relationship('User', backref='weight_logs')
    
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    muscle_group = db.Column(db.String(50))
    category = db.Column(db.String(50))
    description = db.Column(db.String(200))

class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    duration_min = db.Column(db.Integer)
    notes = db.Column(db.String(200))
    
    user = db.relationship('User', backref='workouts')
    sets = db.relationship('WorkoutSet', backref='workout', lazy=True, cascade='all, delete-orphan')

class WorkoutSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    sets = db.Column(db.Integer)
    reps = db.Column(db.Integer)
    weight_kg = db.Column(db.Float)
    
    exercise = db.relationship('Exercise', backref='workout_sets')
    
class WorkoutPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    user = db.relationship('User', backref='workout_plans')
    exercises = db.relationship('PlanExercise', backref='plan', lazy=True, cascade='all, delete-orphan')

class PlanExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('workout_plan.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    day_of_week = db.Column(db.Integer)  # 0=Monday, 6=Sunday
    sets = db.Column(db.Integer, default=3)
    reps = db.Column(db.Integer, default=10)
    target_weight = db.Column(db.Float)  # Suggested weight
    order = db.Column(db.Integer, default=0)
    
    exercise = db.relationship('Exercise', backref='plan_exercises')