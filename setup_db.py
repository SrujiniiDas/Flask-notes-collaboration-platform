# setup_db.py
from website import create_app, db
from website.models import User, Note, ClassRoom

app = create_app()

with app.app_context():
    # 1️⃣ Create database tables if they don't exist
    print("Creating all tables...")
    db.create_all()
    print("Tables created successfully!")

    # 2️⃣ Verify version one changes
    print("\n--- Verifying data ---")

    # Check if there are any users
    users = User.query.all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"User: {u.id} | {u.email} | {u.first_name} | Role: {u.role}")

    # Check if there are any notes
    notes = Note.query.all()
    print(f"\nTotal notes: {len(notes)}")
    for n in notes:
        print(f"Note: {n.id} | Title: {n.title} | Owner: {n.user_id}")

    # Check if classrooms exist
    classrooms = ClassRoom.query.all()
    print(f"\nTotal classrooms: {len(classrooms)}")
    for c in classrooms:
        print(f"ClassRoom: {c.id} | Name: {c.name} | Teacher: {c.teacher_id}")

print("\n✅ Database setup and verification complete!")
