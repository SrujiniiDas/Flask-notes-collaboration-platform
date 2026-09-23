from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from .models import Note, Tag, ClassRoom, ClassPost, Message, User, Comment, Reaction, ClassChatMessage, Poll, PollOption, PollVote, NoteAttachment, NoteHistory
from . import db
import uuid
import json
import bleach

views = Blueprint('views', __name__)


ALLOWED_NOTE_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "ol", "ul", "li",
    "blockquote", "h1", "h2", "h3", "a"
]
ALLOWED_NOTE_ATTRIBUTES = {"a": ["href", "title", "target", "rel"]}


def _sanitize_note_html(value: str) -> str:
    return bleach.clean(
        value or "",
        tags=ALLOWED_NOTE_TAGS,
        attributes=ALLOWED_NOTE_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


# --------- Helpers ---------

def dm_room_id(user1_id: int, user2_id: int) -> str:
    """Stable room ID for a pair of users."""
    a, b = sorted([user1_id, user2_id])
    return f"dm_{a}_{b}"


# --------- Context processor: unread messages badge ---------

@views.app_context_processor
def inject_unread_message_count():
    if current_user.is_authenticated:
        count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    else:
        count = 0
    return {'unread_messages': count}


def _emit_unread_count(user_id: int):
    """Broadcast unread count to a user's personal room."""
    count = Message.query.filter_by(receiver_id=user_id, is_read=False).count()
    return count


# --------- HOME: latest class notes feed ---------

@views.route('/')
@login_required
def home():
    """Personal dashboard with notes, classes, messages, and recent activity."""
    teaching = ClassRoom.query.filter_by(teacher_id=current_user.id).all()
    classes_for_user = list(current_user.joined_classes)
    for classroom in teaching:
        if classroom not in classes_for_user:
            classes_for_user.append(classroom)

    class_ids = [c.id for c in classes_for_user]
    recent_posts = []
    if class_ids:
        recent_posts = (
            ClassPost.query
            .filter(ClassPost.classroom_id.in_(class_ids))
            .order_by(ClassPost.timestamp.desc())
            .limit(6)
            .all()
        )

    recent_notes = (
        Note.query.filter_by(user_id=current_user.id)
        .order_by(Note.pinned.desc(), Note.timestamp.desc())
        .limit(5)
        .all()
    )
    popular_public = (
        Note.query.filter(Note.is_public.is_(True), Note.user_id != current_user.id)
        .order_by(Note.timestamp.desc())
        .limit(4)
        .all()
    )

    stats = {
        'notes': Note.query.filter_by(user_id=current_user.id).count(),
        'public_notes': Note.query.filter_by(user_id=current_user.id, is_public=True).count(),
        'pinned_notes': Note.query.filter_by(user_id=current_user.id, pinned=True).count(),
        'classes': len(classes_for_user),
        'unread': Message.query.filter_by(receiver_id=current_user.id, is_read=False).count(),
    }

    return render_template(
        'home.html',
        user=current_user,
        stats=stats,
        recent_notes=recent_notes,
        recent_posts=recent_posts,
        classes_for_user=classes_for_user[:4],
        popular_public=popular_public,
    )


# --------- MY NOTES ---------

@views.route('/my-notes')
@login_required
def my_notes():
    q = (request.args.get('q') or '').strip()
    tag_name = (request.args.get('tag') or '').strip()
    visibility = (request.args.get('visibility') or 'all').strip()
    sort = (request.args.get('sort') or 'newest').strip()

    query = Note.query.filter_by(user_id=current_user.id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Note.title.ilike(like), Note.content.ilike(like)))
    if tag_name:
        query = query.join(Note.tags).filter(Tag.name == tag_name)
    if visibility == 'public':
        query = query.filter(Note.is_public.is_(True))
    elif visibility == 'private':
        query = query.filter(Note.is_public.is_(False))
    elif visibility == 'pinned':
        query = query.filter(Note.pinned.is_(True))

    if sort == 'oldest':
        query = query.order_by(Note.timestamp.asc())
    elif sort == 'title':
        query = query.order_by(Note.title.asc())
    else:
        query = query.order_by(Note.pinned.desc(), Note.timestamp.desc())

    notes = query.all()
    available_tags = (
        Tag.query.join(Tag.notes)
        .filter(Note.user_id == current_user.id)
        .distinct()
        .order_by(Tag.name.asc())
        .all()
    )
    return render_template(
        'my_notes.html', user_notes=notes, user=current_user, q=q,
        tag_name=tag_name, visibility=visibility, sort=sort, available_tags=available_tags
    )


# --------- CREATE NOTE ---------

@views.route('/create-note', methods=['GET', 'POST'])
@login_required
def create_note():
    if request.method == 'POST':
        data = request.form.get('note')
        title = (request.form.get('title') or 'Untitled').strip()[:255]
        tags_list = request.form.get('tags', '').split(',')
        is_public = bool(request.form.get('is_public'))
        pinned = bool(request.form.get('pinned'))
        upload = request.files.get('attachment')

        if not data or len(data.strip()) < 1:
            flash('Note is too short', category='danger')
        else:
            new_note = Note(
                title=title,
                content=_sanitize_note_html(data),
                user_id=current_user.id,
                share_link=uuid.uuid4().hex[:12],
                is_public=is_public,
                pinned=pinned
            )

            seen_tags = set()
            for raw_tag in tags_list[:12]:
                t = raw_tag.strip()[:50]
                key = t.lower()
                if t and key not in seen_tags:
                    seen_tags.add(key)
                    tag = Tag.query.filter(func.lower(Tag.name) == key).first()
                    if not tag:
                        tag = Tag(name=t)
                        db.session.add(tag)
                    new_note.tags.append(tag)

            db.session.add(new_note)
            db.session.commit()

            if upload and upload.filename:
                _save_note_attachment(new_note, upload)
                db.session.commit()
            flash('Note created successfully', category='success')
            return redirect(url_for('views.my_notes'))

    return render_template('create_note.html', user=current_user)


# --------- DELETE NOTE ---------

@views.route('/delete-note', methods=['POST'])
@login_required
def delete_note():
    data = request.get_json() or {}
    note_id = data.get('noteId')
    if not note_id:
        return jsonify(success=False, error='Missing note ID'), 400

    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify(success=False, error='Not allowed'), 403

    upload_dir = current_app.config.get('UPLOAD_FOLDER')
    if upload_dir:
        for attachment in list(note.attachments):
            file_path = os.path.join(upload_dir, attachment.filepath)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

    NoteHistory.query.filter_by(note_id=note.id).delete(synchronize_session=False)
    db.session.delete(note)
    db.session.commit()
    return jsonify(success=True)

# -------------------- VIEW NOTE PAGE --------------------
@views.route('/note/<int:note_id>')
@login_required
def view_note(note_id):
    note = Note.query.get_or_404(note_id)

    # Only owner or public can view
    if note.user_id != current_user.id and not note.is_public:
        flash("You don't have access to this note.", "error")
        return redirect(url_for("views.my_notes"))

    comments = Comment.query.filter_by(note_id=note.id, parent_id=None).order_by(Comment.timestamp.asc()).all()
    return render_template("view_note.html", note=note, comments=comments)

# ----------------------------------------------------
# EDIT NOTE PAGE  (GET shows form, POST saves changes)
# ----------------------------------------------------
@views.route('/edit-note/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note_page(note_id):
    note = Note.query.get_or_404(note_id)

    # Only the note owner can edit
    if note.user_id != current_user.id:
        flash("You do not have permission to edit this note.", "error")
        return redirect(url_for('views.my_notes'))

    if request.method == "POST":
        new_title = (request.form.get("title") or "Untitled").strip()
        new_content = _sanitize_note_html(request.form.get("content"))

        # Preserve a compact version snapshot before changing meaningful content.
        if new_title != (note.title or "") or new_content != (note.content or ""):
            snapshot = json.dumps({"title": note.title or "Untitled", "content": note.content or ""})
            db.session.add(NoteHistory(note_id=note.id, content_snapshot=snapshot))

        note.title = new_title
        note.content = new_content
        note.is_public = bool(request.form.get("is_public"))
        note.pinned = bool(request.form.get("pinned"))
        if note.is_public and not note.share_link:
            note.share_link = uuid.uuid4().hex[:12]

        tag_names = [t.strip() for t in (request.form.get('tags') or '').split(',') if t.strip()]
        note.tags.clear()
        for tag_name in tag_names[:12]:
            tag = Tag.query.filter(func.lower(Tag.name) == tag_name.lower()).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            note.tags.append(tag)

        upload = request.files.get('attachment')
        if upload and upload.filename:
            _save_note_attachment(note, upload)

        db.session.commit()
        flash("Note updated successfully!", "success")
        return redirect(url_for('views.view_note', note_id=note.id))

    return render_template("edit_note.html", note=note)


@views.route('/note/<int:note_id>/duplicate', methods=['POST'])
@login_required
def duplicate_note(note_id):
    source = Note.query.get_or_404(note_id)
    if source.user_id != current_user.id and not source.is_public:
        return jsonify(success=False, error='Not allowed'), 403

    copy = Note(
        title=f"{source.title or 'Untitled'} (Copy)",
        content=source.content,
        user_id=current_user.id,
        share_link=uuid.uuid4().hex[:12],
        is_public=False,
        pinned=False,
    )
    copy.tags = list(source.tags)
    db.session.add(copy)
    db.session.commit()
    flash('Note duplicated to your workspace.', 'success')
    return redirect(url_for('views.edit_note_page', note_id=copy.id))


@views.route('/note/<int:note_id>/toggle-pin', methods=['POST'])
@login_required
def toggle_note_pin(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify(success=False, error='Not allowed'), 403
    note.pinned = not note.pinned
    db.session.commit()
    return jsonify(success=True, pinned=note.pinned)


@views.route('/note/<int:note_id>/history')
@login_required
def note_history(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('Only the note owner can view version history.', 'danger')
        return redirect(url_for('views.view_note', note_id=note.id))
    versions = (NoteHistory.query.filter_by(note_id=note.id)
                .order_by(NoteHistory.timestamp.desc()).limit(30).all())
    parsed_versions = []
    for version in versions:
        try:
            payload = json.loads(version.content_snapshot)
            title = payload.get('title', note.title)
            content = payload.get('content', '')
        except (TypeError, json.JSONDecodeError, AttributeError):
            title = note.title
            content = version.content_snapshot
        parsed_versions.append({'record': version, 'title': title, 'content': content})
    return render_template('note_history.html', note=note, versions=parsed_versions)


@views.route('/note/<int:note_id>/history/<int:history_id>/restore', methods=['POST'])
@login_required
def restore_note_version(note_id, history_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify(success=False, error='Not allowed'), 403
    version = NoteHistory.query.filter_by(id=history_id, note_id=note.id).first_or_404()
    # Save the current state before restoring an older one.
    db.session.add(NoteHistory(
        note_id=note.id,
        content_snapshot=json.dumps({'title': note.title or 'Untitled', 'content': note.content or ''})
    ))
    try:
        payload = json.loads(version.content_snapshot)
        note.title = payload.get('title', note.title)
        note.content = payload.get('content', note.content)
    except (TypeError, json.JSONDecodeError, AttributeError):
        note.content = version.content_snapshot
    db.session.commit()
    flash('Previous version restored.', 'success')
    return redirect(url_for('views.view_note', note_id=note.id))


@views.route('/note/<int:note_id>/regenerate-share-link', methods=['POST'])
@login_required
def regenerate_share_link(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify(success=False, error='Not allowed'), 403
    note.share_link = uuid.uuid4().hex[:12]
    db.session.commit()
    flash('A new share link was generated.', 'success')
    return redirect(url_for('views.view_note', note_id=note.id))


@views.route('/share/<string:share_link>')
def shared_note(share_link):
    note = Note.query.filter_by(share_link=share_link, is_public=True).first_or_404()
    return render_template('shared_note.html', note=note)


@views.route('/share/<string:share_link>/attachments/<int:attachment_id>')
def shared_attachment(share_link, attachment_id):
    note = Note.query.filter_by(share_link=share_link, is_public=True).first_or_404()
    att = NoteAttachment.query.filter_by(id=attachment_id, note_id=note.id).first_or_404()
    upload_dir = current_app.config.get('UPLOAD_FOLDER') or os.path.join(current_app.root_path, '..', 'uploads')
    return send_from_directory(upload_dir, att.filepath, as_attachment=True, download_name=att.filename)


@views.route('/explore')
@login_required
def explore():
    q = (request.args.get('q') or '').strip()
    query = Note.query.filter(Note.is_public.is_(True), Note.user_id != current_user.id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Note.title.ilike(like), Note.content.ilike(like)))
    notes = query.order_by(Note.pinned.desc(), Note.timestamp.desc()).limit(60).all()
    return render_template('explore.html', notes=notes, q=q)


# --------- COMMENTS API ---------

@views.route('/add-comment', methods=['POST'])
@login_required
def add_comment():
    data = request.get_json() or {}
    note_id = data.get('noteId')
    content = (data.get('content') or '').strip()[:1200]
    parent_id = data.get('parentId')

    if not note_id or not content:
        return jsonify(success=False, error="Missing note or content"), 400

    note = Note.query.get(note_id)
    if not note:
        return jsonify(success=False, error="Note not found"), 404

    # Only owner or public notes can be commented
    if note.user_id != current_user.id and not note.is_public:
        return jsonify(success=False, error="Not allowed"), 403

    parent_comment = None
    if parent_id:
        parent_comment = Comment.query.get(parent_id)
        if not parent_comment or parent_comment.note_id != note.id:
            return jsonify(success=False, error="Invalid parent comment"), 400

    new_comment = Comment(
        note_id=note.id,
        user_id=current_user.id,
        parent_id=parent_id,
        content=content
    )
    db.session.add(new_comment)
    db.session.commit()

    return jsonify(
        success=True,
        author_name=current_user.first_name or current_user.email,
        timestamp=new_comment.timestamp.strftime('%Y-%m-%d %H:%M')
    )


# --------- REACTIONS API ---------

@views.route('/add-reaction', methods=['POST'])
@login_required
def add_reaction():
    data = request.get_json() or {}
    note_id = data.get('noteId')
    reaction_type = data.get('type')

    if reaction_type not in ('like', 'dislike'):
        return jsonify(success=False, error="Invalid reaction"), 400

    note = Note.query.get(note_id)
    if not note:
        return jsonify(success=False, error="Note not found"), 404

    if note.user_id != current_user.id and not note.is_public:
        return jsonify(success=False, error="Not allowed"), 403

    existing = Reaction.query.filter_by(user_id=current_user.id, note_id=note.id).first()
    if existing:
        existing.type = reaction_type
    else:
        db.session.add(Reaction(user_id=current_user.id, note_id=note.id, type=reaction_type))

    db.session.commit()

    counts = {
        'likes': Reaction.query.filter_by(note_id=note.id, type='like').count(),
        'dislikes': Reaction.query.filter_by(note_id=note.id, type='dislike').count(),
    }
    return jsonify(success=True, counts=counts)




# --------- CLASSES LIST ---------

@views.route('/classes')
@login_required
def classes():
    joined = current_user.joined_classes
    teaching = ClassRoom.query.filter_by(teacher_id=current_user.id).order_by(ClassRoom.name.asc()).all()
    return render_template('classes.html', joined=joined, teaching=teaching, user=current_user)


@views.route('/classes/create', methods=['POST'])
@login_required
def create_classroom():
    if current_user.role != 'teacher' and not current_user.is_admin:
        flash('Teacher access is required to create a class.', 'danger')
        return redirect(url_for('views.classes'))

    name = (request.form.get('name') or '').strip()
    if len(name) < 3:
        flash('Class name must be at least 3 characters.', 'danger')
        return redirect(url_for('views.classes'))

    for _ in range(10):
        code = uuid.uuid4().hex[:6].upper()
        if not ClassRoom.query.filter_by(code=code).first():
            break
    classroom = ClassRoom(name=name, code=code, teacher_id=current_user.id)
    db.session.add(classroom)
    db.session.commit()
    flash(f'Class created. Join code: {code}', 'success')
    return redirect(url_for('views.class_feed', class_id=classroom.id))


# --------- CLASS FEED ---------

@views.route('/class/<int:class_id>')
@login_required
def class_feed(class_id):
    classroom = ClassRoom.query.get_or_404(class_id)
    if (current_user not in classroom.students) and (current_user.id != classroom.teacher_id) and (not current_user.is_admin):
        flash('Access Denied to this class', category='danger')
        return redirect(url_for('views.home'))

    posts = sorted(classroom.posts, key=lambda p: p.timestamp or datetime.min, reverse=True)
    return render_template('class_feed.html', classroom=classroom, user=current_user, posts=posts)


@views.route('/class/<int:class_id>/chat')
@login_required
def class_chat(class_id):
    classroom = ClassRoom.query.get_or_404(class_id)
    if (current_user not in classroom.students) and (current_user.id != classroom.teacher_id) and (not current_user.is_admin):
        flash('Access Denied to this class', category='danger')
        return redirect(url_for('views.home'))

    chat_messages = ClassChatMessage.query.filter_by(classroom_id=classroom.id)\
        .order_by(ClassChatMessage.timestamp.asc()).limit(200).all()
    polls = Poll.query.filter_by(classroom_id=classroom.id).order_by(Poll.timestamp.desc()).limit(10).all()

    return render_template(
        'class_chat.html',
        classroom=classroom,
        chat_messages=chat_messages,
        polls=polls,
        user=current_user
    )


# --------- MESSAGES INDEX: list of users ---------

@views.route('/messages', methods=['GET'])
@login_required
def messages_index():
    users = User.query.filter(User.id != current_user.id).order_by(User.first_name.asc()).all()
    return render_template('messages_index.html', users=users, user=current_user)


# --------- MESSAGES PAGE: chat with specific user ---------

@views.route('/messages/<int:user_id>', methods=['GET'])
@login_required
def messages(user_id):
    other_user = User.query.get_or_404(user_id)

    # sidebar list with unread counts
    sidebar_users = User.query.filter(User.id != current_user.id).order_by(User.first_name.asc()).all()
    unread_rows = (
        db.session.query(Message.sender_id, func.count(Message.id))
        .filter(Message.receiver_id == current_user.id, Message.is_read.is_(False))
        .group_by(Message.sender_id)
        .all()
    )
    unread_map = {sid: count for sid, count in unread_rows}

    # load last 50 messages between both users
    msgs_query = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.desc()).limit(50).all()
    msgs = list(reversed(msgs_query))  # show newest while keeping chronological order

    # mark messages to current_user as read
    changed = False
    for m in msgs:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
            changed = True
    if changed:
        db.session.commit()

    return render_template(
        'messages.html',
        messages=msgs,
        other_user=other_user,
        user=current_user,
        sidebar_users=sidebar_users,
        unread_map=unread_map
    )


@views.route('/messages/<int:user_id>/send', methods=['POST'])
@login_required
def messages_send(user_id):
    """HTTP fallback to send a DM (used if socket not connected)."""
    other_user = User.query.get_or_404(user_id)
    content = (request.json or {}).get('content', '').strip()[:2000]
    if not content:
        return jsonify(success=False, error="Message is empty"), 400

    msg = Message(
        sender_id=current_user.id,
        receiver_id=other_user.id,
        content=content,
        is_read=False
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify(
        success=True,
        message={
            'id': msg.id,
            'sender_id': msg.sender_id,
            'receiver_id': msg.receiver_id,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M'),
        }
    )


@views.route('/messages/<int:user_id>/feed', methods=['GET'])
@login_required
def messages_feed(user_id):
    """HTTP pollable feed of last 50 messages between users."""
    other_user = User.query.get_or_404(user_id)
    after_id = request.args.get('after', type=int)
    msgs_query = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    )
    if after_id:
        msgs_query = msgs_query.filter(Message.id > after_id)

    msgs_query = msgs_query.order_by(Message.timestamp.asc()).limit(200).all()
    msgs = list(msgs_query)
    return jsonify([{
        'id': m.id,
        'sender_id': m.sender_id,
        'receiver_id': m.receiver_id,
        'content': m.content,
        'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
    } for m in msgs])


# --------- CLASS CHAT API ---------

def _classroom_access_or_403(classroom_id):
    classroom = ClassRoom.query.get_or_404(classroom_id)
    if (current_user not in classroom.students) and (current_user.id != classroom.teacher_id) and (not current_user.is_admin):
        return None
    return classroom


def _save_note_attachment(note: Note, upload):
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'doc', 'docx'}
    filename = secure_filename(upload.filename)
    if not filename:
        return
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed:
        flash('File type not allowed', 'danger')
        return

    upload_dir = current_app.config.get('UPLOAD_FOLDER') or os.path.join(current_app.root_path, '..', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    dest = os.path.join(upload_dir, unique_name)
    upload.save(dest)

    attach = NoteAttachment(
        note_id=note.id,
        filename=filename,
        filepath=unique_name,
        mimetype=upload.mimetype,
        size=os.path.getsize(dest)
    )
    db.session.add(attach)


@views.route('/class/join', methods=['POST'])
@login_required
def join_class_by_code():
    code = (request.form.get('code') or '').strip().upper()
    classroom = ClassRoom.query.filter_by(code=code).first()
    if not classroom:
        flash('Invalid class code', 'danger')
        return redirect(url_for('views.classes'))
    if current_user not in classroom.students:
        classroom.students.append(current_user)
        db.session.commit()
        flash(f'Joined {classroom.name}', 'success')
    else:
        flash('You are already in this class.', 'info')
    return redirect(url_for('views.class_feed', class_id=classroom.id))


@views.route('/class/<int:class_id>/remove-student/<int:user_id>', methods=['POST'])
@login_required
def remove_student(class_id, user_id):
    classroom = ClassRoom.query.get_or_404(class_id)
    if (current_user.id != classroom.teacher_id) and (not current_user.is_admin):
        flash('Only teacher or admin can remove students', 'danger')
        return redirect(url_for('views.class_feed', class_id=class_id))
    student = User.query.get_or_404(user_id)
    if student in classroom.students:
        classroom.students.remove(student)
        db.session.commit()
        flash(f'Removed {student.first_name or student.email}', 'success')
    return redirect(url_for('views.class_feed', class_id=class_id))


@views.route('/class/<int:class_id>/chat/send', methods=['POST'])
@login_required
def class_chat_send(class_id):
    classroom = _classroom_access_or_403(class_id)
    if not classroom:
        return jsonify(success=False, error="Access denied"), 403
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()[:2000]
    if not content:
        return jsonify(success=False, error="Message empty"), 400

    msg = ClassChatMessage(classroom_id=classroom.id, user_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()

    return jsonify(success=True, message={
        'id': msg.id,
        'user_id': msg.user_id,
        'content': msg.content,
        'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M'),
        'author': current_user.first_name or current_user.email
    })


@views.route('/class/<int:class_id>/chat/feed')
@login_required
def class_chat_feed(class_id):
    classroom = _classroom_access_or_403(class_id)
    if not classroom:
        return jsonify([]), 403
    after_id = request.args.get('after', type=int)
    qs = ClassChatMessage.query.filter_by(classroom_id=classroom.id)
    if after_id:
        qs = qs.filter(ClassChatMessage.id > after_id)
    msgs = qs.order_by(ClassChatMessage.timestamp.asc()).limit(200).all()
    return jsonify([{
        'id': m.id,
        'user_id': m.user_id,
        'author': m.user.first_name or m.user.email,
        'content': m.content,
        'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
    } for m in msgs])


@views.route('/class/<int:class_id>/polls', methods=['POST'])
@login_required
def class_create_poll(class_id):
    classroom = _classroom_access_or_403(class_id)
    if not classroom:
        return jsonify(success=False, error="Access denied"), 403
    if (current_user.id != classroom.teacher_id) and (not current_user.is_admin):
        return jsonify(success=False, error="Only teacher/admin can create polls"), 403

    data = request.get_json() or {}
    question = bleach.clean((data.get('question') or '').strip(), tags=[], strip=True)[:255]
    options = data.get('options') or []
    options = [bleach.clean(o.strip(), tags=[], strip=True)[:200] for o in options if o and o.strip()]

    if not question or len(options) < 2:
        return jsonify(success=False, error="Question and at least 2 options required"), 400

    poll = Poll(question=question, classroom_id=classroom.id, created_by=current_user.id)
    db.session.add(poll)
    db.session.flush()
    for opt in options[:6]:
        db.session.add(PollOption(poll_id=poll.id, text=opt))
    db.session.commit()

    return jsonify(success=True, poll_id=poll.id)


@views.route('/class/<int:class_id>/polls/<int:poll_id>/vote', methods=['POST'])
@login_required
def class_poll_vote(class_id, poll_id):
    classroom = _classroom_access_or_403(class_id)
    if not classroom:
        return jsonify(success=False, error="Access denied"), 403

    poll = Poll.query.filter_by(id=poll_id, classroom_id=classroom.id).first_or_404()
    data = request.get_json() or {}
    option_id = data.get('option_id')
    option = PollOption.query.filter_by(id=option_id, poll_id=poll.id).first()
    if not option:
        return jsonify(success=False, error="Invalid option"), 400

    # one vote per poll per user
    existing = (
        db.session.query(PollVote)
        .join(PollOption)
        .filter(PollOption.poll_id == poll.id, PollVote.user_id == current_user.id)
        .first()
    )
    if existing:
        existing.option_id = option.id
    else:
        db.session.add(PollVote(option_id=option.id, user_id=current_user.id))

    db.session.commit()

    # return counts
    counts = {
        opt.id: len(opt.votes)
        for opt in poll.options
    }
    return jsonify(success=True, counts=counts)


@views.route('/class/<int:class_id>/post', methods=['POST'])
@login_required
def create_class_post(class_id):
    classroom = ClassRoom.query.get_or_404(class_id)
    if (current_user.id != classroom.teacher_id) and (not current_user.is_admin):
        flash('Only teacher or admin can post to the class feed.', 'danger')
        return redirect(url_for('views.class_feed', class_id=class_id))

    content = bleach.clean((request.form.get('content') or '').strip(), tags=[], strip=True)[:5000]
    title = bleach.clean((request.form.get('title') or '').strip(), tags=[], strip=True)[:255]
    if not content:
        flash('Post content is required.', 'danger')
        return redirect(url_for('views.class_feed', class_id=class_id))

    post = ClassPost(
        title=title or None,
        content=content,
        user_id=current_user.id,
        classroom_id=classroom.id
    )
    db.session.add(post)
    db.session.commit()
    flash('Post added to class feed.', 'success')
    return redirect(url_for('views.class_feed', class_id=class_id))


@views.route('/messages/<int:user_id>/read', methods=['POST'])
@login_required
def messages_mark_read(user_id):
    """Mark messages from given user as read (HTTP fallback)."""
    other_user = User.query.get_or_404(user_id)
    msgs = Message.query.filter_by(
        sender_id=other_user.id,
        receiver_id=current_user.id,
        is_read=False
    ).all()
    changed = False
    for m in msgs:
        m.is_read = True
        changed = True
    if changed:
        db.session.commit()
    return jsonify(success=True, unread=Message.query.filter_by(receiver_id=current_user.id, is_read=False).count())


@views.route('/messages/unread-summary', methods=['GET'])
@login_required
def messages_unread_summary():
    """Return total unread and per-sender counts."""
    rows = (
        db.session.query(Message.sender_id, func.count(Message.id))
        .filter(Message.receiver_id == current_user.id, Message.is_read.is_(False))
        .group_by(Message.sender_id)
        .all()
    )
    per_sender = {sid: count for sid, count in rows}
    total = sum(per_sender.values())
    return jsonify(total=total, per_sender=per_sender)


@views.route('/attachments/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    att = NoteAttachment.query.get_or_404(attachment_id)
    note = att.note
    if note.user_id != current_user.id and not note.is_public:
        flash("You don't have access to this file.", 'danger')
        return redirect(url_for('views.home'))
    upload_dir = current_app.config.get('UPLOAD_FOLDER') or os.path.join(current_app.root_path, '..', 'uploads')
    return send_from_directory(upload_dir, att.filepath, as_attachment=True, download_name=att.filename)


@views.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        action = request.form.get('action', 'profile')
        if action == 'profile':
            first_name = (request.form.get('first_name') or '').strip()
            if len(first_name) < 2:
                flash('Display name must be at least 2 characters.', 'danger')
            else:
                current_user.first_name = first_name
                db.session.commit()
                flash('Profile updated.', 'success')
                return redirect(url_for('views.account'))
        elif action == 'password':
            current_password = request.form.get('current_password') or ''
            new_password = request.form.get('new_password') or ''
            confirm_password = request.form.get('confirm_password') or ''
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'danger')
            elif len(new_password) < 8:
                flash('New password must be at least 8 characters.', 'danger')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
            else:
                current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
                db.session.commit()
                flash('Password changed successfully.', 'success')
                return redirect(url_for('views.account'))
    return render_template('account.html', user=current_user)


@views.route('/health')
def health():
    return jsonify(status='ok', service='collabnotes')


# --------- USER SEARCH (AJAX for messages.html search box) ---------

@views.route('/user-search')
@login_required
def user_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    users = User.query.filter(
        User.id != current_user.id,
        or_(User.first_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"))
    ).order_by(User.first_name.asc()).limit(10).all()

    return jsonify([
        {'id': u.id, 'first_name': u.first_name, 'email': u.email}
        for u in users
    ])


