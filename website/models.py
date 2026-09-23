from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

# ---------------------
# Association Tables
# ---------------------

tags_notes_association = db.Table(
    'tags_notes',
    db.Column('note_id', db.Integer, db.ForeignKey('note.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

classroom_students = db.Table(
    'classroom_students',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('class_room.id'), primary_key=True)
)


# ---------------------
# Models
# ---------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(150))
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(50), default="student")  # student/teacher/admin

    # Relationships
    notes = db.relationship('Note', back_populates='owner', lazy=True)
    joined_classes = db.relationship(
        'ClassRoom',
        secondary=classroom_students,
        back_populates='students'
    )
    sent_messages = db.relationship(
        'Message',
        foreign_keys='Message.sender_id',
        backref='sender',
        lazy=True
    )
    received_messages = db.relationship(
        'Message',
        foreign_keys='Message.receiver_id',
        backref='receiver',
        lazy=True
    )
    class_posts = db.relationship('ClassPost', back_populates='author', lazy=True)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    pinned = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False)
    share_link = db.Column(db.String(255), unique=True, nullable=True)

    # Replace date with timestamp for consistency
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
    date = db.synonym('timestamp')   # Jinja compatibility

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    owner = db.relationship('User', back_populates='notes')
    tags = db.relationship('Tag', secondary=tags_notes_association, back_populates='notes')
    reactions = db.relationship('Reaction', back_populates='note', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', back_populates='note', lazy=True, cascade="all, delete-orphan")
    attachments = db.relationship('NoteAttachment', back_populates='note', lazy=True, cascade="all, delete-orphan")


class NoteHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'))
    content_snapshot = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())


class NoteAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'))
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    mimetype = db.Column(db.String(100))
    size = db.Column(db.Integer)

    note = db.relationship('Note', back_populates='attachments')


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    notes = db.relationship('Note', secondary=tags_notes_association, back_populates='tags')


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)
    reactions = db.relationship('Reaction', back_populates='comment', lazy=True, cascade="all, delete-orphan")
    note = db.relationship('Note', back_populates='comments')
    author = db.relationship('User')


class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))  # e.g., like, love, etc.
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    user = db.relationship('User')
    note = db.relationship('Note', back_populates='reactions')
    comment = db.relationship('Comment', back_populates='reactions')


class ClassRoom(db.Model):
    __tablename__ = 'class_room'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    code = db.Column(db.String(50), unique=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    students = db.relationship(
        'User',
        secondary=classroom_students,
        back_populates='joined_classes'
    )
    posts = db.relationship('ClassPost', back_populates='classroom', lazy=True)
    chat_messages = db.relationship('ClassChatMessage', back_populates='classroom', lazy=True, cascade="all, delete-orphan")
    polls = db.relationship('Poll', back_populates='classroom', lazy=True, cascade="all, delete-orphan")


class ClassPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)

    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
    date = db.synonym('timestamp')   # For template compatibility

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    classroom_id = db.Column(db.Integer, db.ForeignKey('class_room.id'))

    author = db.relationship('User', back_populates='class_posts')
    classroom = db.relationship('ClassRoom', back_populates='posts')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())
    # NEW: for unread badge
    is_read = db.Column(db.Boolean, default=False)


class ClassChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('class_room.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())

    classroom = db.relationship('ClassRoom', back_populates='chat_messages')
    user = db.relationship('User')


class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    classroom_id = db.Column(db.Integer, db.ForeignKey('class_room.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())

    classroom = db.relationship('ClassRoom', back_populates='polls')
    options = db.relationship('PollOption', back_populates='poll', cascade="all, delete-orphan", lazy=True)
    creator = db.relationship('User')


class PollOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'))
    text = db.Column(db.String(200), nullable=False)

    poll = db.relationship('Poll', back_populates='options')
    votes = db.relationship('PollVote', back_populates='option', cascade="all, delete-orphan", lazy=True)


class PollVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    option = db.relationship('PollOption', back_populates='votes')
    user = db.relationship('User')
