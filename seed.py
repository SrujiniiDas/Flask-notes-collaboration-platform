# FILE: seed.py (Final Fixed Version)

from werkzeug.security import generate_password_hash
from website import create_app, db
from sqlalchemy.sql import func
from sqlalchemy.orm import attributes 
from sqlalchemy import text 

# Import models/tables
from website.models import (
    User, Note, ClassRoom, ClassPost, Tag, Message, Reaction, Comment, NoteHistory,
    ClassChatMessage, Poll, PollOption, PollVote, NoteAttachment,
    tags_notes_association, classroom_students
)

# ================================
# FIX 1: Define TEST_PASSWORD
# ================================
TEST_PASSWORD = "password123"

tags_notes = tags_notes_association


# ================================
# INITIAL SCHEMA CREATION
# ================================
def create_initial_schema(app):
    with app.app_context():
        db.create_all()
        db.session.commit()
        print("--- Initial Schema COMMIT successful. ---")

        db.session.close()
        db.engine.dispose()
        print("--- Database engine disposed for fresh connection. ---")


# ================================
# SEED DATA
# ================================
def create_seed_data(app):
    with app.app_context():
        print("Starting database seeding...")

        # Clear tables
        # Order matters for FKs
        tables = [
            "poll_vote", "poll_option", "poll", "class_chat_message",
            "message", "reaction", "comment", "note_attachment", "note_history",
            "tags_notes", "classroom_students",
            "class_post", "note", "tag", "class_room", "user"
        ]

        for table in tables:
            db.session.execute(text(f"DELETE FROM {table}"))

        db.session.commit()
        print("-> Cleared all tables.")

        # Create users
        hashed_password = generate_password_hash(TEST_PASSWORD, method='pbkdf2:sha256')

        admin_user = User(
            email="admin@app.com",
            password=hashed_password,
            first_name="Admin",
            is_admin=True,
            role="admin"
        )
        teacher_user = User(
            email="teacher@app.com",
            password=hashed_password,
            first_name="Professor Ada",
            role="teacher"
        )
        student_user = User(
            email="student@app.com",
            password=hashed_password,
            first_name="Student Ben",
            role="student"
        )

        db.session.add_all([admin_user, teacher_user, student_user])
        db.session.commit()
        print("-> Created admin, teacher, student users.")

        # Create tags
        tag_flask = Tag(name="Flask")
        tag_testing = Tag(name="Testing")
        tag_public = Tag(name="Public")

        # FIX 2: Correct private tag
        tag_private = Tag(name="Private")

        db.session.add_all([tag_flask, tag_testing, tag_public, tag_private])
        db.session.commit()
        print("-> Created 4 tags.")

        # Create notes
        note_public_teacher = Note(
            title="Lecture 1 Summary (Public)",
            content="<p>This explains SQLAlchemy relationships.</p>",
            is_public=True,
            share_link="lecture-1-demo",
            user_id=teacher_user.id
        )
        note_private_student = Note(
            title="My Private Draft",
            content="<p>Private project notes...</p>",
            is_public=False,
            share_link="private-draft-demo",
            user_id=student_user.id
        )
        note_pinned_admin = Note(
            title="Pinned Announcement",
            content="<p>Welcome to FlaskNotes!</p>",
            pinned=True,
            is_public=True,
            share_link="welcome-demo",
            user_id=admin_user.id
        )

        db.session.add_all([note_public_teacher, note_private_student, note_pinned_admin])
        db.session.flush()

        # Assign tags
        note_public_teacher.tags = [tag_flask, tag_public]
        note_private_student.tags = [tag_private]
        note_pinned_admin.tags = [tag_testing, tag_public]

        db.session.commit()
        print("-> Created 3 notes with tags.")

        # Create classes
        class_101 = ClassRoom(name="CS 101 - Introduction to Python", teacher_id=teacher_user.id, code="PY101")
        class_201 = ClassRoom(name="CS 201 - Web Backend", teacher_id=teacher_user.id, code="WEB201")
        db.session.add_all([class_101, class_201])
        db.session.commit()

        class_101.students.append(student_user)
        class_201.students.append(student_user)
        db.session.commit()
        print("-> Added student to classes.")

        # Class posts
        posts = [
            ClassPost(content="Assignment 1 is due Friday.", user_id=teacher_user.id, classroom_id=class_101.id),
            ClassPost(content="Office hours: Wednesday at 2pm.", user_id=teacher_user.id, classroom_id=class_101.id),
            ClassPost(content="Project kickoff slides have been uploaded.", user_id=teacher_user.id, classroom_id=class_201.id),
        ]
        db.session.add_all(posts)
        db.session.commit()
        print("-> Created class posts.")

        # Class chat messages
        chat_messages = [
            ClassChatMessage(classroom_id=class_101.id, user_id=teacher_user.id, content="Welcome to CS101!"),
            ClassChatMessage(classroom_id=class_101.id, user_id=student_user.id, content="Excited to learn!"),
            ClassChatMessage(classroom_id=class_201.id, user_id=teacher_user.id, content="Backend course kicks off next week."),
        ]
        db.session.add_all(chat_messages)
        db.session.commit()
        print("-> Created class chat messages.")

        # Polls
        poll1 = Poll(question="When should we hold a review session?", classroom_id=class_101.id, created_by=teacher_user.id)
        db.session.add(poll1)
        db.session.flush()
        poll1_opts = [
            PollOption(poll_id=poll1.id, text="Monday 5pm"),
            PollOption(poll_id=poll1.id, text="Tuesday 5pm"),
            PollOption(poll_id=poll1.id, text="Friday 3pm"),
        ]
        db.session.add_all(poll1_opts)
        db.session.commit()
        print("-> Created polls with options.")

        # Votes
        vote1 = PollVote(option_id=poll1_opts[0].id, user_id=student_user.id)
        vote2 = PollVote(option_id=poll1_opts[1].id, user_id=teacher_user.id)
        db.session.add_all([vote1, vote2])
        db.session.commit()
        print("-> Recorded sample poll votes.")

        # Direct messages
        dm1 = Message(sender_id=teacher_user.id, receiver_id=student_user.id, content="Welcome to the course!", is_read=False)
        dm2 = Message(sender_id=student_user.id, receiver_id=teacher_user.id, content="Thanks, looking forward!", is_read=False)
        db.session.add_all([dm1, dm2])
        db.session.commit()
        print("-> Seeded direct messages.")

        print("SEEDING COMPLETE!")
        print("Login emails:\n admin@app.com\n teacher@app.com\n student@app.com")
        print("Password:", TEST_PASSWORD)


# ================================
# RUN
# ================================
if __name__ == "__main__":
    app = create_app()
    create_initial_schema(app)
    create_seed_data(app)
