from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db, login_manager
from app.models import User, WeightLog, Exercise, Workout, WorkoutSet
from datetime import datetime
import requests

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

@bp.route('/log-workout', methods=['GET', 'POST'])
@login_required
def log_workout():
    if request.method == 'POST':
        try:
            # Get form data
            date = request.form.get('date')
            duration_min = request.form.get('duration_min')
            notes = request.form.get('notes', '')
            
            # Get exercise data from form
            exercise_names = request.form.getlist('exercise_name[]')
            sets_list = request.form.getlist('sets[]')
            reps_list = request.form.getlist('reps[]')
            weights_list = request.form.getlist('weight[]')
            
            # Validate
            if not exercise_names or len(exercise_names) == 0:
                flash('Please add at least one exercise', 'danger')
                return render_template('log_workout.html')
            
            # Create workout
            workout = Workout(
                user_id=current_user.id,
                date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.now(),
                duration_min=int(duration_min) if duration_min else 0,
                notes=notes
            )
            db.session.add(workout)
            db.session.flush()
            
            # Add sets
            for i in range(len(exercise_names)):
                exercise_name = exercise_names[i].strip()
                if not exercise_name:
                    continue
                
                # Find or create exercise
                exercise = Exercise.query.filter_by(name=exercise_name).first()
                if not exercise:
                    exercise = Exercise(
                        name=exercise_name,
                        muscle_group='Unknown',
                        category='Unknown'
                    )
                    db.session.add(exercise)
                    db.session.flush()
                
                workout_set = WorkoutSet(
                    workout_id=workout.id,
                    exercise_id=exercise.id,
                    sets=int(sets_list[i]) if sets_list and i < len(sets_list) and sets_list[i] else 3,
                    reps=int(reps_list[i]) if reps_list and i < len(reps_list) and reps_list[i] else 10,
                    weight_kg=float(weights_list[i]) if weights_list and i < len(weights_list) and weights_list[i] else 0
                )
                db.session.add(workout_set)
            
            db.session.commit()
            flash('Workout logged successfully! 💪', 'success')
            return redirect(url_for('main.workout_history'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return render_template('log_workout.html')
    
    # Pass today's date to the template
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('log_workout.html', today=today)


@bp.route('/workout-history')
@login_required
def workout_history():
    workouts = Workout.query.filter_by(user_id=current_user.id).order_by(Workout.date.desc()).all()
    return render_template('workout_history.html', workouts=workouts)
@bp.route('/api/exercises/search')
def search_exercises():
    """Search exercises from wger API - only return exercises with images"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify([])
    
    try:
        url = f'https://wger.de/api/v2/exerciseinfo/?format=json&language=2&limit=1000'
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for ex in data.get('results', []):
                # Check if exercise has images FIRST
                images = ex.get('images', [])
                if not images:
                    continue  # Skip exercises without images
                
                # Get English name from translations
                name = None
                for t in ex.get('translations', []):
                    if t.get('language') == 2:  # English
                        name = t.get('name')
                        break
                
                if not name:
                    continue
                
                if query.lower() in name.lower():
                    # Get image
                    image_url = None
                    thumbnail_url = None
                    
                    for img in images:
                        if img.get('is_main'):
                            image_url = img.get('image')
                            thumbnails = img.get('thumbnails', {})
                            thumbnail_url = thumbnails.get('small') or thumbnails.get('medium')
                            break
                    
                    # If no main image, use first available
                    if not image_url and images:
                        image_url = images[0].get('image')
                        thumbnails = images[0].get('thumbnails', {})
                        thumbnail_url = thumbnails.get('small') or thumbnails.get('medium')
                    
                    results.append({
                        'id': ex.get('id'),
                        'name': name,
                        'muscle_group': 'Various',
                        'image': image_url,
                        'thumbnail': thumbnail_url
                    })
            
            return jsonify(results[:20])
        
        return jsonify([])
        
    except Exception as e:
        print(f"Exercise search error: {str(e)}")
        return jsonify([])

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.login'))