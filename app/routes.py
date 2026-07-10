from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db, login_manager
from app.models import User, WeightLog, Exercise, Workout, WorkoutSet, WorkoutPlan, PlanExercise
from datetime import datetime, timedelta
import requests

bp = Blueprint('main', __name__)

# ============================================
# HELPERS
# ============================================

def user_has_setup(user):
    """Check if user has completed profile setup"""
    return user.height_cm is not None and user.goal_weight is not None

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================
# AUTH ROUTES
# ============================================

@bp.route('/')
def index():
    if current_user.is_authenticated:
        if not user_has_setup(current_user):
            return redirect(url_for('main.setup'))
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

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
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('register.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.login'))


# ============================================
# SETUP
# ============================================

@bp.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
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
            
            current_user.height_cm = height
            current_user.goal_weight = goal_weight
            
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


# ============================================
# DASHBOARD
# ============================================

@bp.route('/dashboard')
@login_required
def dashboard():
    if not user_has_setup(current_user):
        return redirect(url_for('main.setup'))
    
    # Get latest weight
    latest_weight = WeightLog.query.filter_by(user_id=current_user.id).order_by(WeightLog.date.desc()).first()
    
    # Calculate streak
    streak = 0
    if current_user.workouts:
        check_date = datetime.now().date()
        while True:
            day_workouts = Workout.query.filter(
                Workout.user_id == current_user.id,
                db.func.date(Workout.date) == check_date
            ).count()
            if day_workouts > 0:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
    
    # Calculate BMI
    bmi = None
    bmi_interpretation = None
    if latest_weight and current_user.height_cm:
        height_m = current_user.height_cm / 100
        bmi = latest_weight.weight_kg / (height_m ** 2)
        
        if bmi < 18.5:
            bmi_interpretation = "Underweight"
        elif bmi < 25:
            bmi_interpretation = "Normal"
        elif bmi < 30:
            bmi_interpretation = "Overweight"
        else:
            bmi_interpretation = "Obese"
    
    return render_template('dashboard.html', 
        user=current_user,
        latest_weight=latest_weight,
        streak=streak,
        bmi=bmi,
        bmi_interpretation=bmi_interpretation
    )


# ============================================
# WORKOUT LOGGING
# ============================================

@bp.route('/log-workout', methods=['GET', 'POST'])
@login_required
def log_workout():
    if request.method == 'POST':
        try:
            date = request.form.get('date')
            duration_min = request.form.get('duration_min')
            notes = request.form.get('notes', '')
            
            exercise_names = request.form.getlist('exercise_name[]')
            sets_list = request.form.getlist('sets[]')
            reps_list = request.form.getlist('reps[]')
            weights_list = request.form.getlist('weight[]')
            
            if not exercise_names or len(exercise_names) == 0:
                flash('Please add at least one exercise', 'danger')
                return render_template('log_workout.html')
            
            workout = Workout(
                user_id=current_user.id,
                date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.now(),
                duration_min=int(duration_min) if duration_min else 0,
                notes=notes
            )
            db.session.add(workout)
            db.session.flush()
            
            for i in range(len(exercise_names)):
                exercise_name = exercise_names[i].strip()
                if not exercise_name:
                    continue
                
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
    
    today = datetime.now().strftime('%Y-%m-%d')
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    return render_template('log_workout.html', today=today, plans=plans)

@bp.route('/workout-history')
@login_required
def workout_history():
    workouts = Workout.query.filter_by(user_id=current_user.id).order_by(Workout.date.desc()).all()
    return render_template('workout_history.html', workouts=workouts)

@bp.route('/workout/<int:workout_id>/delete', methods=['POST'])
@login_required
def delete_workout(workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first_or_404()
    WorkoutSet.query.filter_by(workout_id=workout.id).delete()
    db.session.delete(workout)
    db.session.commit()
    flash('Workout deleted successfully', 'info')
    return redirect(url_for('main.workout_history'))

@bp.route('/workout-set/<int:set_id>/delete', methods=['POST'])
@login_required
def delete_workout_set(set_id):
    workout_set = WorkoutSet.query.get(set_id)
    if not workout_set:
        flash('Set not found', 'danger')
        return redirect(url_for('main.workout_history'))
    
    workout = Workout.query.get(workout_set.workout_id)
    if not workout or workout.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('main.workout_history'))
    
    db.session.delete(workout_set)
    db.session.commit()
    flash('Exercise set deleted', 'info')
    return redirect(url_for('main.workout_history'))


# ============================================
# WEIGHT LOGGING
# ============================================

@bp.route('/log-weight', methods=['GET', 'POST'])
@login_required
def log_weight():
    if request.method == 'POST':
        weight = request.form.get('weight')
        notes = request.form.get('notes', '')
        
        if not weight:
            flash('Please enter a weight', 'danger')
            return render_template('log_weight.html')
        
        try:
            weight = float(weight)
            if weight <= 0:
                flash('Please enter a valid weight', 'danger')
                return render_template('log_weight.html')
            
            weight_log = WeightLog(
                user_id=current_user.id,
                weight_kg=weight,
                notes=notes
            )
            db.session.add(weight_log)
            db.session.commit()
            
            flash('Weight logged successfully! ⚖️', 'success')
            return redirect(url_for('main.weight_history'))
            
        except ValueError:
            flash('Please enter a valid number', 'danger')
            return render_template('log_weight.html')
    
    return render_template('log_weight.html')

@bp.route('/weight-history')
@login_required
def weight_history():
    logs = WeightLog.query.filter_by(user_id=current_user.id).order_by(WeightLog.date.asc()).all()
    return render_template('weight_history.html', logs=logs)

@bp.route('/weight/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_weight(log_id):
    log = WeightLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    flash('Weight entry deleted', 'info')
    return redirect(url_for('main.weight_history'))


# ============================================
# WORKOUT PLANS
# ============================================

@bp.route('/plans')
@login_required
def plans():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()
    return render_template('plans.html', plans=plans)

@bp.route('/plans/create', methods=['GET', 'POST'])
@login_required
def create_plan():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('Plan name is required', 'danger')
            return render_template('create_plan.html')
        
        plan = WorkoutPlan(
            user_id=current_user.id,
            name=name,
            description=description
        )
        db.session.add(plan)
        db.session.flush()
        
        exercise_names = request.form.getlist('exercise_name[]')
        sets_list = request.form.getlist('sets[]')
        reps_list = request.form.getlist('reps[]')
        weights_list = request.form.getlist('target_weight[]')
        days_list = request.form.getlist('day_of_week[]')
        
        for i in range(len(exercise_names)):
            if not exercise_names[i].strip():
                continue
            
            exercise = Exercise.query.filter_by(name=exercise_names[i].strip()).first()
            if not exercise:
                exercise = Exercise(
                    name=exercise_names[i].strip(),
                    muscle_group='Unknown',
                    category='Unknown'
                )
                db.session.add(exercise)
                db.session.flush()
            
            plan_exercise = PlanExercise(
                plan_id=plan.id,
                exercise_id=exercise.id,
                sets=int(sets_list[i]) if sets_list and i < len(sets_list) and sets_list[i] else 3,
                reps=int(reps_list[i]) if reps_list and i < len(reps_list) and reps_list[i] else 10,
                target_weight=float(weights_list[i]) if weights_list and i < len(weights_list) and weights_list[i] else None,
                day_of_week=int(days_list[i]) if days_list and i < len(days_list) and days_list[i] else None,
                order=i
            )
            db.session.add(plan_exercise)
        
        db.session.commit()
        flash('Workout plan created successfully! 💪', 'success')
        return redirect(url_for('main.plans'))
    
    return render_template('create_plan.html')

@bp.route('/plans/<int:plan_id>/start')
@login_required
def start_plan(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('log_plan_workout.html', plan=plan, today=today)

@bp.route('/plans/<int:plan_id>/log', methods=['POST'])
@login_required
def log_plan_workout(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    try:
        date = request.form.get('date')
        duration_min = request.form.get('duration_min')
        notes = request.form.get('notes', '')
        
        workout = Workout(
            user_id=current_user.id,
            date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.now(),
            duration_min=int(duration_min) if duration_min else 0,
            notes=notes
        )
        db.session.add(workout)
        db.session.flush()
        
        plan_exercise_ids = request.form.getlist('plan_exercise_id[]')
        actual_sets = request.form.getlist('actual_sets[]')
        actual_reps = request.form.getlist('actual_reps[]')
        actual_weights = request.form.getlist('actual_weight[]')
        
        for i in range(len(plan_exercise_ids)):
            if not plan_exercise_ids[i]:
                continue
            
            plan_exercise = PlanExercise.query.get(int(plan_exercise_ids[i]))
            if not plan_exercise:
                continue
            
            workout_set = WorkoutSet(
                workout_id=workout.id,
                exercise_id=plan_exercise.exercise_id,
                sets=int(actual_sets[i]) if actual_sets and i < len(actual_sets) and actual_sets[i] else 3,
                reps=int(actual_reps[i]) if actual_reps and i < len(actual_reps) and actual_reps[i] else 10,
                weight_kg=float(actual_weights[i]) if actual_weights and i < len(actual_weights) and actual_weights[i] else 0
            )
            db.session.add(workout_set)
        
        db.session.commit()
        flash('Workout logged successfully! 💪', 'success')
        return redirect(url_for('main.workout_history'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('main.start_plan', plan_id=plan_id))

@bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete_plan(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    db.session.delete(plan)
    db.session.commit()
    flash('Plan deleted', 'info')
    return redirect(url_for('main.plans'))


# ============================================
# API ENDPOINTS
# ============================================

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
                images = ex.get('images', [])
                if not images:
                    continue
                
                name = None
                for t in ex.get('translations', []):
                    if t.get('language') == 2:
                        name = t.get('name')
                        break
                
                if not name:
                    continue
                
                if query.lower() in name.lower():
                    image_url = None
                    thumbnail_url = None
                    
                    for img in images:
                        if img.get('is_main'):
                            image_url = img.get('image')
                            thumbnails = img.get('thumbnails', {})
                            thumbnail_url = thumbnails.get('small') or thumbnails.get('medium')
                            break
                    
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

@bp.route('/api/weight-data')
@login_required
def weight_data():
    """Return weight data as JSON for charts"""
    logs = WeightLog.query.filter_by(user_id=current_user.id).order_by(WeightLog.date.asc()).all()
    
    data = {
        'dates': [log.date.strftime('%Y-%m-%d') for log in logs],
        'weights': [log.weight_kg for log in logs],
        'goal': current_user.goal_weight
    }
    return jsonify(data)

@bp.route('/api/plan/<int:plan_id>/exercises')
@login_required
def get_plan_exercises(plan_id):
    """Get exercises for a specific plan"""
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    exercises = []
    plan_exercises = PlanExercise.query.filter_by(plan_id=plan.id).order_by(PlanExercise.order).all()
    
    for pe in plan_exercises:
        exercise = Exercise.query.get(pe.exercise_id)
        if exercise:
            exercises.append({
                'id': pe.id,
                'name': exercise.name,
                'sets': pe.sets,
                'reps': pe.reps,
                'target_weight': pe.target_weight
            })
        else:
            exercises.append({
                'id': pe.id,
                'name': f"Exercise {pe.exercise_id}",
                'sets': pe.sets,
                'reps': pe.reps,
                'target_weight': pe.target_weight
            })
    
    return jsonify({'exercises': exercises})