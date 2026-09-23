from werkzeug.security import generate_password_hash
from website import db
from website.models import ClassRoom, Note, User


def make_user(email="student@example.com", role="student", admin=False):
    user = User(
        email=email,
        first_name="Test User",
        password=generate_password_hash("password123"),
        role=role,
        is_admin=admin,
    )
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email="student@example.com", password="password123"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_signup_always_creates_student(client, app):
    response = client.post(
        "/signup",
        data={
            "email": "new@example.com",
            "firstName": "New Student",
            "password1": "password123",
            "password2": "password123",
            "role": "admin",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="new@example.com").one()
        assert user.role == "student"
        assert user.is_admin is False


def test_private_note_is_not_visible_to_other_user(client, app):
    with app.app_context():
        owner = make_user("owner@example.com")
        other = make_user("other@example.com")
        note = Note(title="Private", content="secret", user_id=owner.id, is_public=False)
        db.session.add(note)
        db.session.commit()
        note_id = note.id

    login(client, "other@example.com")
    response = client.get(f"/note/{note_id}", follow_redirects=False)
    assert response.status_code == 302


def test_public_share_page_does_not_require_login(client, app):
    with app.app_context():
        owner = make_user("owner@example.com")
        note = Note(
            title="Shared note",
            content="<p>Hello</p>",
            user_id=owner.id,
            is_public=True,
            share_link="share-token",
        )
        db.session.add(note)
        db.session.commit()

    response = client.get("/share/share-token")
    assert response.status_code == 200
    assert b"Shared note" in response.data


def test_student_cannot_create_classroom(client, app):
    with app.app_context():
        make_user()
    login(client)
    response = client.post("/classes/create", data={"name": "Restricted Class"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert ClassRoom.query.count() == 0


def test_teacher_can_create_classroom(client, app):
    with app.app_context():
        make_user("teacher@example.com", role="teacher")
    login(client, "teacher@example.com")
    response = client.post("/classes/create", data={"name": "Software Engineering"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        classroom = ClassRoom.query.one()
        assert classroom.name == "Software Engineering"
        assert len(classroom.code) == 6
