import os
import random
from ortools.sat.python import cp_model
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url)

# Positions
server = 0
runner = 1
host = 2
busser = 3
bartender = 4
catering = 5
cook = 6
all_positions = [server, runner, host]

num_employees = 10
num_shifts = 3
num_days = 7
all_employees = range(num_employees)
all_shifts = range(num_shifts)
all_days = range(num_days)

none_request = 0
am_request = 1
pm_request = 2
dbl_request = 3

max_minutes = 40 * 60 # 40 hours (in minutes) per employee weekly

employee_roles = {}
for e in all_employees:
    employee_roles[e] = []

# DATA FROM THE SQL EMPLOYEES TABLE YAY
employee_ids = []
target_minutes = []
seniority_scores = []
historical_minutes = [] # 4-week rolling basis (USE A QUEUE-FIFO DELETE 1 EVERY WEEK)

# Row = Employee;   Column = Day;   Element = Shift (AM/PM/DBL)
shift_availability = [[none_request for d in all_days] for e in all_employees]

# Each item tracks open shifts on the calender to be filled
house_shifts = []

# Pulling info from database
with engine.connect() as connection:
    employees_table = connection.execute(text("SELECT id, target_minutes_per_week, seniority_score, historical_minutes FROM employees ORDER BY id ASC"))
    for row in employees_table:
        employee_ids.append(row[0])
        target_minutes.append(int(row[1]))
        seniority_scores.append(int(row[2]))
        historical_minutes.append(int(row[3]))

    employee_roles_table = connection.execute(text("SELECT employee_id, role_id FROM employee_roles ORDER BY employee_id ASC"))
    for row in employee_roles_table:
        current_employee_id = int(row[0])
        role_id = int(row[1])
        employee_roles[current_employee_id].append(role_id)

    shift_requests_table = connection.execute(text("SELECT employee_id, day_of_week, request_type FROM shift_requests"))
    for row in shift_requests_table:
        current_employee_id = int(row[0])
        day = int(row[1])
        req_type = int(row[2])
        shift_availability[current_employee_id][day] = req_type

    house_shifts_table = connection.execute(text("SELECT id, day_of_week, role_id, start_minutes, end_minutes, is_weekend_rate FROM house_shifts"))
    for row in house_shifts_table:
        shift_blueprint = {
            "id": int(row[0]),
            "day": int(row[1]),
            "role": int(row[2]),
            "start": int(row[3]),
            "end": int(row[4])
        }
        house_shifts.append(shift_blueprint)


model = cp_model.CpModel()


# shifts[(e, d, s)]: employee 'e' works shift 's'
shifts = {}
for e in all_employees:
    for s in house_shifts:
        shift_id = s["id"]
        shifts[(e, s["id"])] = model.new_bool_var(f"assign_e{e}_shift{shift_id}")

# Every open shift can only recieve at most one employee
for s in house_shifts:
    assigned_pool = []
    for e in all_employees:
        assigned_pool.append(shifts[(e, s["id"])])
    model.add(cp_model.LinearExpr.sum(assigned_pool) <= 1)

# Employees can only be scheduled for qualified position(s)
for e in all_employees:
    for s in house_shifts:
        if s["role"] not in employee_roles[e]:
            model.add(shifts[(e, s["id"])] == 0)

# Employees can only be scheduled when they request that shift
for e in all_employees:
    for s in house_shifts:
        shift_id = s["id"]
        d = s["day"]
        is_am_shift = s["start"] < 1020  # True if shift starts before 5:00 PM

        employee_request = shift_availability[e][d]
        has_am_request = employee_request == am_request
        has_pm_request = employee_request == pm_request
        has_dbl_request = employee_request == dbl_request

        if is_am_shift and not has_am_request and not has_dbl_request:
            model.add(shifts[(e, shift_id)] == 0)
        elif not is_am_shift and not has_pm_request and not has_dbl_request:
            model.add(shifts[(e, shift_id)] == 0)

# Prevents against scheduling overlapping shifts
for e in all_employees:
    for shift1 in house_shifts:
        for shift2 in house_shifts:
            if shift1["id"] >= shift2["id"] or shift1["day"] != shift2["day"]:
                continue
            overlaps = (shift1["start"] < shift2["end"]) and (shift2["start"] < shift1["end"])
            if overlaps:
                model.add(shifts[(e, shift1["id"])] + shifts[(e, shift2["id"])] <= 1)

# Employees cannot work more than 40 hours (2400 minutes) per week
for e in all_employees:
    mins_worked = []
    for s in house_shifts:
        duration = s["end"] - s["start"]
        mins_worked.append(shifts[(e, s["id"])] * duration)
    model.add(cp_model.LinearExpr.sum(mins_worked) <= max_minutes)

# This handles workforce fairness, employee seniority, and random tie-breaking
# It separates preference fulfillment (1000 pts) from priority scores to
# ensure the solver can rank employees cleanly
objective_terms = []
for e in all_employees:
    weekly_average_mins = historical_minutes[e] / 4.0
    fairness_gap = int(target_minutes[e] - weekly_average_mins)
    seniority_bonus = seniority_scores[e] * 120
    noise = random.randint(0, 1200)

    for s in house_shifts:
        shift_id = s["id"]
        d = s["day"]
        is_am_shift = s["start"] < 1020

        user_request = shift_availability[e][d]
        if is_am_shift:
            is_requested = (user_request == am_request) or (user_request == dbl_request)
        else:
            is_requested = (user_request == pm_request) or (user_request == dbl_request)

        base_reward = 100000 * int(is_requested) * shifts[(e, s["id"])]
        fairness_points = (fairness_gap + seniority_bonus + noise) * shifts[(e, s["id"])]
        objective_terms.append(base_reward + fairness_points)

model.maximize(sum(objective_terms))

solver = cp_model.CpSolver()
status = solver.solve(model)

if status == cp_model.OPTIMAL:
    print("Optimal Schedule Generated, uploading to database.\n")
    role_names = {server: "Server", runner: "Runner", host: "Host"}

    with engine.connect() as connection:
        connection.execute(text("TRUNCATE TABLE finalized_schedule CASCADE;"))
        for shift in house_shifts:
            shift_id = shift["id"]
            role = role_names[shift["role"]]
            day = shift["day"]
            start = shift["start"] / 60.0
        
            filled = False
            for e in all_employees:
                if solver.value(shifts[(e, shift_id)]) == 1:
                    print(f"Day {day} | Shift ID {shift_id} ({role}, Start: {start:.1f}): Assigned to Employee {e}")
                    finalized_schedule = {"shift_id": int(shift_id), "employee_id": int(e), "is_published": False}
                    connection.execute(text("""INSERT INTO finalized_schedule (shift_id, employee_id, is_published)
                        VALUES (:shift_id, :employee_id, :is_published)"""), finalized_schedule)
                    filled = True
                    break
            if not filled:
                #print(f"Day {day} | Shift ID {shift_id} ({role}, Start: {start:.1f}): UNFILLED (Staff Shortage)")
                finalized_schedule = {"shift_id": int(shift_id), "employee_id": None, "is_published": False}
                connection.execute(text("""INSERT INTO finalized_schedule (shift_id, employee_id, is_published)
                    VALUES (:shift_id, :employee_id, :is_published)"""), finalized_schedule)
        connection.commit()    
else:
    print("No optimal schedule found.")

engine.dispose()


# FUTURE ME: to prevent score inflation from absent weeks, calculate
# dynamic_target_shifts from both requested and target
# and change fairness_gap to fairness_ratio (actual/dynamic_target)
# which should be close to 1
# historical_workload will hold dynamic_target, and also add
# is_absent so we can ignore that week of data.
# employee table will pull from historical workloads
# Also, add in AM/PM (either) option as a shift request. 
# Also, shift staggering will happen before sent to house_shifts
# 
