from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db, login_manager
from app.models import User, WeightLog  # ← ADD WeightLog import

bp = Blueprint('main', __name__)

def user_has_setup(user):
    """Check if user has completed profile setup"""
    return user.height_cm is not None and user.goal_weight is not None


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@bp.route('/')
def index():
    if current_user.is_authenticated:
        if not user_has_setup(current_user):
            return redirect(url_for('main.setup'))
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    if not user_has_setup(current_user):
        return redirect(url_for('main.setup'))
    return render_template('dashboard.html', user=current_user)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            # Check if user needs setup
            if not user_has_setup(user):
                return redirect(url_for('main.setup'))
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create user
        user = User(
            username=username,
            email=email
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('register.html')

@bp.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    # If user already has setup, redirect to dashboard
    if user_has_setup(current_user):
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        if 'skip' in request.form:
            flash('You can complete your profile later.', 'info')
            return redirect(url_for('main.dashboard'))
        
        weight = request.form.get('weight')
        height = request.form.get('height')
        goal_weight = request.form.get('goal_weight')
        
        if not weight or not height or not goal_weight:
            flash('All fields are required!', 'danger')
            return render_template('setup.html')
        
        try:
            weight = float(weight)
            height = float(height)
            goal_weight = float(goal_weight)
            
            # Save user data
            current_user.height_cm = height
            current_user.goal_weight = goal_weight
            
            # Save initial weight log
            weight_log = WeightLog(
                user_id=current_user.id,
                weight_kg=weight,
                notes='Initial weight'
            )
            db.session.add(weight_log)
            db.session.commit()
            
            flash('Profile setup complete! Welcome to your fitness journey! 🎉', 'success')
            return redirect(url_for('main.dashboard'))
            
        except ValueError:
            flash('Please enter valid numbers', 'danger')
            return render_template('setup.html')
    
    return render_template('setup.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.login'))