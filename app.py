from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

# ===== SQLite Configuration - FIXED FOR RENDER =====
# Use /tmp for Render (writable), otherwise use instance folder
if os.environ.get('RENDER'):
    # Ensure /tmp directory exists and is writable
    db_path = '/tmp/kazimoto.db'
    print(f"✅ Running on Render - Using database at: {db_path}")
else:
    # Local development - use instance folder
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, 'kazimoto.db')
    print(f"✅ Running locally - Using database at: {db_path}")

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ===== DATABASE MODELS =====

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    course = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    payment_status = db.Column(db.String(20), default='pending')
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    admin_remarks = db.Column(db.Text, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

# ===== CREATE TABLES =====

with app.app_context():
    db.create_all()
    
    # Create default admin if not exists
    if not Admin.query.filter_by(username='admin').first():
        default_admin = Admin(
            username='admin',
            password=generate_password_hash('admin123')
        )
        db.session.add(default_admin)
        db.session.commit()
        print("✅ Default admin created: admin / admin123")
    
    # Check if musa.kazimoto admin exists, if not create it
    if not Admin.query.filter_by(username='musa.kazimoto').first():
        musa_admin = Admin(
            username='musa.kazimoto',
            password=generate_password_hash('Al1983+,')
        )
        db.session.add(musa_admin)
        db.session.commit()
        print("✅ Admin created: musa.kazimoto / Al1983+, (for Render)")

# ===== ROUTES =====

@app.route('/')
def index():
    """Landing page with profile"""
    return render_template('index.html')

@app.route('/status')
def check_status():
    """Check registration status by email"""
    email = request.args.get('email', '')
    student = None
    if email:
        student = Student.query.filter_by(email=email).first()
    return render_template('student/status.html', student=student, email=email)

# ===== STUDENT ROUTES =====

@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        course = request.form.get('course')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('student_register'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters!', 'error')
            return redirect(url_for('student_register'))
        
        existing = Student.query.filter_by(email=email).first()
        if existing:
            flash('This email is already registered. Please login.', 'error')
            return redirect(url_for('student_login'))
        
        student = Student(
            full_name=full_name,
            email=email,
            phone=phone,
            course=course,
            password=generate_password_hash(password),
            payment_status='pending'
        )
        
        db.session.add(student)
        db.session.commit()
        
        flash(f'✅ Registration Successful! Please login to check your status.', 'success')
        return redirect(url_for('student_login'))
    
    courses = ['Networking Essentials', 'Software Development', 'Artificial Intelligence', 'Cybersecurity', 'Full-Stack Web Development']
    return render_template('student/register.html', courses=courses)

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        student = Student.query.filter_by(email=email).first()
        if student and check_password_hash(student.password, password):
            session['student_logged_in'] = True
            session['student_id'] = student.id
            session['student_name'] = student.full_name
            session['student_email'] = student.email
            flash(f'👋 Welcome back, {student.full_name}!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            flash('❌ Invalid email or password!', 'error')
    
    return render_template('student/login.html')

@app.route('/student/dashboard')
def student_dashboard():
    if not session.get('student_logged_in'):
        return redirect(url_for('student_login'))
    
    student = Student.query.get(session['student_id'])
    return render_template('student/dashboard.html', student=student)

@app.route('/student/logout')
def student_logout():
    session.clear()
    flash('👋 Logged out successfully!', 'info')
    return redirect(url_for('index'))

# ===== ADMIN ROUTES =====

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('✅ Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('❌ Invalid username or password!', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    students = Student.query.order_by(Student.registration_date.desc()).all()
    pending = Student.query.filter_by(payment_status='pending').all()
    verified = Student.query.filter_by(payment_status='verified').all()
    paid = Student.query.filter_by(payment_status='paid').all()
    
    stats = {
        'total': len(students),
        'pending': len(pending),
        'verified': len(verified),
        'paid': len(paid)
    }
    
    return render_template('admin/dashboard.html', students=students, pending=pending, stats=stats)

@app.route('/admin/verify/<int:student_id>', methods=['POST'])
def admin_verify(student_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    student = Student.query.get_or_404(student_id)
    student.payment_status = 'verified'
    student.verified_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'✅ {student.full_name} has been verified successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/verify-paid/<int:student_id>', methods=['POST'])
def admin_verify_paid(student_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    student = Student.query.get_or_404(student_id)
    student.payment_status = 'paid'
    db.session.commit()
    
    flash(f'✅ Payment confirmed for {student.full_name}. Awaiting final verification.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('👋 Logged out successfully!', 'info')
    return redirect(url_for('index'))

@app.route('/admin/delete/<int:student_id>', methods=['POST'])
def admin_delete(student_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    
    flash(f'🗑️ {student.full_name} has been deleted.', 'warning')
    return redirect(url_for('admin_dashboard'))

# ===== CONTEXT PROCESSOR =====

@app.context_processor
def utility_processor():
    return {'now': datetime.now()}

# ===== RUN APP =====

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
