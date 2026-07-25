from ortools.sat.python import cp_model
from typing import Union
import random

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
num_shifts = 7
num_days = 7
all_employees = range(num_employees)
all_shifts = range(num_shifts)
all_days = range(num_days)

am_request = 0
pm_request = 1
dbl_request = 2

max_minutes = 40 * 60   # 40 hours (in minutes) per employee weekly
max_employees = 5  # Per shift

employee_roles = {
    0: [server, runner],
    1: [server],
    2: [server],
    3: [runner, host],
    4: [runner],

    5: [runner],
    6: [host, server],
    7: [host],
    8: [host],
    9: [server, runner, host]
}

tier_1_employees = [0, 1, 2, 3, 4]  # Target: 10 hours/week
tier_2_employees = [5, 6, 7, 8, 9]  # Target: 20 hours/week
tier_3_employees = []               # Target: 30 hours/week
tier_4_employees = []               # Target: 40 hours/week
tier_1_target = 10 * 60
tier_2_target = 20 * 60
tier_3_target = 30 * 60
tier_4_target = 40 * 60

seniority_scores = [0, 0, 0, 0, 0,  0, 0, 0, 0, 0]
historical_minutes_recieved = [0 *60, 0 *60, 0 *60, 0 *60, 0 *60, 
                             0 *60, 0 *60, 0 *60, 0 *60, 0 *60]


# Row = Employee;   Column = Day;   Element = Shift (AM/PM/DBL)
shift_availability = [
    [[0,0,1], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
]

# FUTURE ME: in the case that they arent recieving shifts because they just arent 
# available, compare RECIEVED to tierTarget and REQUESTED. 
# if not, their priority will be high since solver thinks they havent been scheduled,
# and they'll start hogging shifts.
''' (real headcounts)
WEEKENDS        WEEKDAYS
25 AM server    8 AM server
15 AM runner    3 AM runner
6 AM host       4 AM host
30 PM SERVER    15 PM server
16 PM runner    8 PM runner
12 PM host      8 PM host
'''

# Each item tracks open shifts on the calender to be filled
# will eventually pull straight from sql database <- website input
house_shifts = [
    {"id": 101, "day": 0, "role": server, "start": 660,  "end": 1020}, # 11:00 AM - 5:00 PM
    {"id": 102, "day": 0, "role": server, "start": 660,  "end": 1020}, # 11:00 AM - 5:00 PM
    {"id": 103, "day": 0, "role": runner, "start": 660,  "end": 1020}, # 11:00 AM - 5:00 PM
    {"id": 104, "day": 0, "role": runner, "start": 690,  "end": 1020}, # 11:30 AM - 5:00 PM
    {"id": 105, "day": 0, "role": host,   "start": 720,  "end": 1020}, # 12:00 PM - 5:00 PM
]


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

        has_am_request = shift_availability[e][d][am_request] == 1
        has_pm_request = shift_availability[e][d][pm_request] == 1
        has_dbl_request = shift_availability[e][d][dbl_request] == 1

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
    weekly_average_mins = historical_minutes_recieved[e] / 4.0
    if e in tier_1_employees:  tier_target = tier_1_target
    elif e in tier_2_employees:  tier_target = tier_2_target
    elif e in tier_3_employees:  tier_target = tier_3_target
    elif e in tier_4_employees:  tier_target = tier_4_target
    fairness_gap = int(tier_target - weekly_average_mins)
    seniority_bonus = seniority_scores[e] * 120
    noise = random.randint(0, 1200)

    for s in house_shifts:
        shift_id = s["id"]
        d = s["day"]
        is_am_shift = s["start"] < 1020
        if is_am_shift:
            is_requested = (shift_availability[e][d][am_request] == 1) or (shift_availability[e][d][dbl_request] == 1)
        else:
            is_requested = (shift_availability[e][d][pm_request] == 1) or (shift_availability[e][d][dbl_request] == 1)

        base_reward = 100000 * int(is_requested) * shifts[(e, s["id"])]
        fairness_points = (fairness_gap + seniority_bonus + noise) * shifts[(e, s["id"])]
        objective_terms.append(base_reward + fairness_points)

model.maximize(sum(objective_terms))

solver = cp_model.CpSolver()
status = solver.solve(model)

if status == cp_model.OPTIMAL:
    print("Optimal Schedule Generated.\n")
    role_names = {server: "Server", runner: "Runner", host: "Host"}
    for shift in house_shifts:
        shift_id = shift["id"]
        role = role_names[shift["role"]]
        day = shift["day"]
        start = shift["start"] / 60.0
        
        filled = False
        for e in all_employees:
            if solver.value(shifts[(e, shift_id)]) == 1:
                print(f"Day {day} | Shift ID {shift_id} ({role}, Start: {start:.1f}): Assigned to Employee {e}")
                filled = True
                break
        if not filled:
            print(f"Day {day} | Shift ID {shift_id} ({role}, Start: {start:.1f}): UNFILLED (Staff Shortage)")
else:
    print("No optimal schedule found.")





