from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from functools import wraps
from .models import User, Note, ClassRoom, Message
from . import db

admin = Blueprint('admin', __name__)

# -------------------- ADMIN DECORATOR --------------------
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access Denied: Administrators only.', category='error')
            return redirect(url_for('views.home'))
        return f(*args, **kwargs)
    return decorated

# -------------------- DASHBOARD --------------------
@admin.route('/dashboard')
@login_required
@admin_required
def dashboard():
    all_users = User.query.all()
    stats = {
        'users': User.query.count(),
        'notes': Note.query.count(),
        'public_notes': Note.query.filter_by(is_public=True).count(),
        'classes': ClassRoom.query.count(),
        'messages': Message.query.count(),
    }
    return render_template('admin_dashboard.html', users=all_users, stats=stats)

# -------------------- DELETE USER --------------------
@admin.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.is_admin:
        flash("Cannot delete an administrator account.", category='error')
        return redirect(url_for('admin.dashboard'))

    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'User {user_to_delete.email} successfully deleted.', category='success')
    return redirect(url_for('admin.dashboard'))


@admin.route('/user/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def update_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Administrator roles are protected.', 'danger')
        return redirect(url_for('admin.dashboard'))
    role = (request.form.get('role') or '').strip().lower()
    if role not in {'student', 'teacher'}:
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.dashboard'))
    user.role = role
    db.session.commit()
    flash(f'{user.email} is now a {role}.', 'success')
    return redirect(url_for('admin.dashboard'))
