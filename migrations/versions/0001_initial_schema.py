"""Initial CollabNotes schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("password", sa.String(length=150), nullable=False),
        sa.Column("first_name", sa.String(length=150), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "class_room",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "note",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=True),
        sa.Column("share_link", sa.String(length=255), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.UniqueConstraint("share_link"),
    )
    op.create_table(
        "class_post",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("class_room.id"), nullable=True),
    )
    op.create_table(
        "message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("receiver_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=True),
    )
    op.create_table(
        "comment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("note.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("comment.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "note_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("note.id"), nullable=True),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "note_attachment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("note.id"), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("filepath", sa.String(length=255), nullable=False),
        sa.Column("mimetype", sa.String(length=100), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
    )
    op.create_table(
        "class_chat_message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("class_room.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_table(
        "poll",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question", sa.String(length=255), nullable=False),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("class_room.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_table(
        "poll_option",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poll_id", sa.Integer(), sa.ForeignKey("poll.id"), nullable=True),
        sa.Column("text", sa.String(length=200), nullable=False),
    )
    op.create_table(
        "poll_vote",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("option_id", sa.Integer(), sa.ForeignKey("poll_option.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
    )
    op.create_table(
        "reaction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("note.id"), nullable=True),
        sa.Column("comment_id", sa.Integer(), sa.ForeignKey("comment.id"), nullable=True),
    )
    op.create_table(
        "tags_notes",
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("note.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tag.id"), primary_key=True),
    )
    op.create_table(
        "classroom_students",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), primary_key=True),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("class_room.id"), primary_key=True),
    )


def downgrade():
    for table in [
        "classroom_students", "tags_notes", "reaction", "poll_vote", "poll_option", "poll",
        "class_chat_message", "note_attachment", "note_history", "comment", "message",
        "class_post", "note", "class_room", "tag", "user"
    ]:
        op.drop_table(table)
