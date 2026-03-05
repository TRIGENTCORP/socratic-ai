from database import init_db, add_student
from datetime import datetime

init_db()

add_student('TEST001', 'A', datetime.now().isoformat())
add_student('TEST002', 'B', datetime.now().isoformat())
add_student('TEST003', 'A', datetime.now().isoformat())

print('Test students created!')
print('Login with: TEST001 (System A), TEST002 (System B), TEST003 (System A)')
