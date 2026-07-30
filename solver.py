import os
import random
from ortools.sat.python import cp_model
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List, Dict

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

# Request types
none_request = 0
am_request = 1
pm_request = 2
dbl_request = 3

max_minutes = 40 * 60 # 40 hours (in minutes) per employee weekly

@dataclass
class Employee:
    id: int
    name: str
    target_minutes: int
    seniority_score: int
    historical_minutes: int
    roles: List[int] = field(default_factory = list)
    availability: Dict[int, int] = field(default_factory = dict)

@dataclass
class HouseShift:
    id: int
    day: int
    role: int
    start: int
    end: int
    is_weekend: bool

@dataclass
class FinalizedSchedule:
    shift_id: int
    employee_id: int
    is_published: bool = False

all_employees = []
house_shifts = []
employee_lookup = {} # { employee_id: employee }
employee_history = {} # { employee_id: [ {"minutes": 1080, "absent": false}, ... ] }


# Pulling info from database
with engine.connect() as connection:
    employees_table = connection.execute(text("SELECT id, name, target_minutes_per_week, seniority_score, historical_minutes FROM employees ORDER BY id ASC")).mappings().all()
    employee_roles_table = connection.execute(text("SELECT employee_id, role_id FROM employee_roles ORDER BY employee_id ASC")).mappings().all()
    shift_requests_table = connection.execute(text("SELECT employee_id, day_of_week, request_type FROM shift_requests")).mappings().all()
    house_shifts_table = connection.execute(text("SELECT id, day_of_week, role_id, start_minutes, end_minutes, is_weekend FROM house_shifts")).mappings().all()
    historical_workloads_table = connection.execute(text("SELECT employee_id, week_offset, minutes_worked, is_absent FROM historical_workloads")).mappings().all()
engine.dispose()

for row in employees_table:
    e_id = row["id"]
    employee = Employee(
        id = e_id, 
        name = row["name"], 
        target_minutes = row["target_minutes_per_week"], 
        seniority_score= row["seniority_score"], 
        historical_minutes = row["historical_minutes"])
    all_employees.append(employee)
    employee_lookup[e_id] = employee
    employee_history[e_id] = []

for row in employee_roles_table:
    if row["employee_id"] in employee_lookup:
        employee_lookup[row["employee_id"]].roles.append(row["role_id"])

for row in shift_requests_table:
    if row["employee_id"] in employee_lookup:
        employee_lookup[row["employee_id"]].availability[row["day_of_week"]] = row["request_type"]

for row in house_shifts_table:
    shift = HouseShift(
        id = row["id"],
        day = row["day_of_week"],
        role = row["role_id"],
        start = row["start_minutes"],
        end = row["end_minutes"],
        is_weekend = row["is_weekend"])
    house_shifts.append(shift)

for row in historical_workloads_table:
    if row["employee_id"] in employee_history:
        employee_history[row["employee_id"]].append({
            "minutes": int(row["minutes_worked"]),
            "absent": bool(row["is_absent"]) })


model = cp_model.CpModel()


# shifts[(e, s)]: employee 'e' works shift 's'
shifts = {}
for e in all_employees:
    for s in house_shifts:
        shifts[(e.id, s.id)] = model.new_bool_var(f"assign_e{e.id}_shift{s.id}")

# Every open shift can only recieve at most one employee
for s in house_shifts:
    assigned = []
    for e in all_employees:
        assigned.append(shifts[(e.id, s.id)])
    model.add(cp_model.LinearExpr.sum(assigned) <= 1)

# Employees can only be scheduled for qualified position(s)
for e in all_employees:
    for s in house_shifts:
        if s.role not in e.roles:
            model.add(shifts[(e.id, s.id)] == 0)

# Employees can only be scheduled when they request that shift
for e in all_employees:
    for s in house_shifts:
        is_am_shift = s.start < 1020  # True if shift starts before 5:00 PM

        employee_request = e.availability.get(s.day, none_request)
        has_am_request = employee_request == am_request
        has_pm_request = employee_request == pm_request
        has_dbl_request = employee_request == dbl_request

        if is_am_shift and not has_am_request and not has_dbl_request:
            model.add(shifts[(e.id, s.id)] == 0)
        elif not is_am_shift and not has_pm_request and not has_dbl_request:
            model.add(shifts[(e.id, s.id)] == 0)

# Prevents against scheduling overlapping shifts
for e in all_employees:
    for shift1 in house_shifts:
        for shift2 in house_shifts:
            if shift1.id >= shift2.id or shift1.day != shift2.day:
                continue
            overlaps = (shift1.start < shift2.end) and (shift2.start < shift1.end)
            if overlaps:
                model.add(shifts[(e.id, shift1.id)] + shifts[(e.id, shift2.id)] <= 1)

# Employees cannot work more than 40 hours (2400 minutes) per week
for e in all_employees:
    mins_worked = []
    for s in house_shifts:
        duration = s.end - s.start
        mins_worked.append(shifts[(e.id, s.id)] * duration)
    model.add(cp_model.LinearExpr.sum(mins_worked) <= max_minutes)

# This handles workforce fairness, employee seniority, and random tie-breaking
# It separates preference fulfillment (1000 pts) from priority scores to
# ensure the solver can rank employees cleanly
objective_terms = []
for e in all_employees:
    minutes_worked = 0
    active_weeks = 0
    for week_record in employee_history.get(e.id, []):
        if not week_record["absent"]:
            minutes_worked += week_record["minutes"]
            active_weeks += 1
    if active_weeks > 0:
        weekly_average_mins = minutes_worked / float(active_weeks)
    else:
        weekly_average_mins = e.target_minutes

    requested_minutes = 0
    for d in range(7):
        request_type = e.availability.get(d, none_request)
        if request_type == am_request or request_type == pm_request:
            requested_minutes += 5 * 60
        elif request_type == dbl_request:
            requested_minutes += 10 * 60

    weekly_target = min(e.target_minutes, requested_minutes)
    fairness_gap = int(weekly_target - weekly_average_mins)
    seniority_bonus = e.seniority_score * 120
    noise = random.randint(0, 1200)

    for s in house_shifts:
        is_am_shift = s.start < 1020

        user_request = e.availability.get(s.day, none_request)
        if is_am_shift:
            is_requested = (user_request == am_request) or (user_request == dbl_request)
        else:
            is_requested = (user_request == pm_request) or (user_request == dbl_request)

        base_reward = 100000 * int(is_requested) * shifts[(e.id, s.id)]
        fairness_points = (fairness_gap + seniority_bonus + noise) * shifts[(e.id, s.id)]
        objective_terms.append(base_reward + fairness_points)

model.maximize(sum(objective_terms))

solver = cp_model.CpSolver()
status = solver.solve(model)

if status == cp_model.OPTIMAL:
    print("Optimal Schedule Generated, uploading to database.\n")
    role_names = {server: "Server", runner: "Runner", host: "Host"}

    with engine.connect() as connection:
        connection.execute(text("TRUNCATE TABLE finalized_schedule CASCADE;"))
        for s in house_shifts:
            role = role_names[s.role]
        
            filled = False
            for e in all_employees:
                if solver.value(shifts[(e.id, s.id)]) == 1:
                    print(f"Day {s.day} | Shift ID {s.id} ({role}, Start: {s.start / 60:.1f}): Assigned to Employee {e.id}")
                    finalized_schedule = {"shift_id": int(s.id), "employee_id": int(e.id), "is_published": False}
                    connection.execute(text("""INSERT INTO finalized_schedule (shift_id, employee_id, is_published)
                        VALUES (:shift_id, :employee_id, :is_published)"""), finalized_schedule)
                    filled = True
                    break
            if not filled:
                print(f"Day {s.day} | Shift ID {s.id} ({role}, Start: {s.start / 60:.1f}): UNFILLED (Staff Shortage)")
                finalized_schedule = {"shift_id": int(s.id), "employee_id": None, "is_published": False}
                connection.execute(text("""INSERT INTO finalized_schedule (shift_id, employee_id, is_published)
                    VALUES (:shift_id, :employee_id, :is_published)"""), finalized_schedule)
        connection.commit()
    engine.dispose()
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
