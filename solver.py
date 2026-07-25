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
allPositions = [server, runner, host]

numEmployees = 10
numShifts = 7
numDays = 7
allEmployees = range(numEmployees)
allShifts = range(numShifts)
allDays = range(numDays)

amRequest = 0
pmRequest = 1
dblRequest = 2

maxMinutes = 40 * 60   # 40 hours (in minutes) per employee weekly
maxEmployees = 5  # Per shift

employeeRoles = {
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

tier1Employees = [0, 1, 2, 3, 4]  # Target: 10 hours/week
tier2Employees = [5, 6, 7, 8, 9]  # Target: 20 hours/week
tier3Employees = [] # Target: 30 hours/week
tier4Employees = [] # Target: 40 hours/week

seniorityScores = [5, 4, 3, 3, 2,  4, 3, 2, 1, 1]
historicalMinutesRecieved = [0, 20*300, 22*300, 21*300, 28*300, 
                             10*300, 6*300, 13*300, 0, 12*300]


# Row = Employee;   Column = Day;   Element = Shift (AM/PM/DBL)
shiftAvailability = [
    [[1,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,0,0]],
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
# will eventually pull straight from manager website input
houseShifts = [
    {"id": 101, "day": 0, "role": server, "start": 660,  "end": 1020}, # 11:00 AM - 5:00 PM
    {"id": 102, "day": 0, "role": server, "start": 660,  "end": 1020}, # 11:00 AM - 5:00 PM
    {"id": 103, "day": 0, "role": runner, "start": 660,  "end": 1020}, # 11:00 AM - 5:00 PM
    {"id": 104, "day": 0, "role": runner, "start": 690,  "end": 1020}, # 11:30 AM - 5:00 PM
    {"id": 105, "day": 0, "role": host,   "start": 720,  "end": 1020}, # 12:00 PM - 5:00 PM
]


model = cp_model.CpModel()


# shifts[(e, d, s)]: employee 'e' works shift 's'
shifts = {}
for e in allEmployees:
    for s in houseShifts:
        shiftId = s["id"]
        shifts[(e, s["id"])] = model.new_bool_var(f"assign_e{e}_shift{shiftId}")

# Every open shift can only recieve at most one employee
for s in houseShifts:
    assignedPool = []
    for e in allEmployees:
        assignedPool = [shifts[(e, s["id"])]]
    model.add(cp_model.LinearExpr.sum(assignedPool) <= 1)

# Employees can only be scheduled for qualified position(s)
for e in allEmployees:
    for s in houseShifts:
        if s["role"] not in employeeRoles[e]:
            model.add(shifts[(e, s["id"])] == 0)

# Employees can only be scheduled when they request that shift
for e in allEmployees:
    for s in houseShifts:
        shiftId = s["id"]
        d = s["day"]
        isAmShift = s["start"] < 1020  # True if shift starts before 5:00 PM

        hasAmRequest = shiftAvailability[e][d][amRequest] == 1
        hasPmRequest = shiftAvailability[e][d][pmRequest] == 1
        hasDblRequest = shiftAvailability[e][d][dblRequest] == 1

        if isAmShift and not hasAmRequest and not hasDblRequest:
            model.add(shifts[(e, shiftId)] == 0)
        elif not isAmShift and not hasPmRequest and not hasDblRequest:
            model.add(shifts[(e, shiftId)] == 0)

# Prevents against scheduling overlapping shifts
for e in allEmployees:
    for shift1 in houseShifts:
        for shift2 in houseShifts:
            if shift1["id"] >= shift2["id"] or shift1["day"] != shift2["day"]:
                continue
            overlaps = (shift1["start"] < shift2["end"]) and (shift2["start"] < shift1["end"])
            if overlaps:
                model.add(shifts[(e, shift1["id"])] + shifts[(e, shift2["id"])] <= 1)

# Employees cannot work more than 40 hours (2400 minutes) per week
for e in allEmployees:
    minsWorked = []
    for s in houseShifts:
        duration = s["end"] - s["start"]
        minsWorked.append(shifts[(e, s["id"])] * duration)
    model.add(cp_model.LinearExpr.sum(minsWorked) <= maxMinutes)

# This handles workforce fairness, employee seniority, and random tie-breaking
# It separates preference fulfillment (1000 pts) from priority scores to 
# ensure the solver can rank employees cleanly
objectiveTerms = []
for e in allEmployees:
    weeklyAverageMins = historicalMinutesRecieved[e] / 4.0
    if e in tier1Employees:
        tierTarget = 1650.0
    else:
        tierTarget = 750.0
    fairnessGap = int(tierTarget - weeklyAverageMins)
    seniorityBonus = seniorityScores[e] * 120
    noise = random.randint(0, 1200) # may increase to 30-50 so teens can beat adults

    for s in houseShifts:
        shiftId = s["id"]
        d = s["day"]
        isAmShift = s["start"] < 1020
        if isAmShift:
            isRequested = (shiftAvailability[e][d][amRequest] == 1) or (shiftAvailability[e][d][dblRequest] == 1)
        else:
            isRequested = (shiftAvailability[e][d][pmRequest] == 1) or (shiftAvailability[e][d][dblRequest] == 1)

        baseReward = 100000 * int(isRequested) * shifts[(e, s["id"])]
        fairnessPoints = (fairnessGap + seniorityBonus + noise) * shifts[(e, s["id"])]
        objectiveTerms.append(baseReward + fairnessPoints)

model.maximize(sum(objectiveTerms))

solver = cp_model.CpSolver()
status = solver.solve(model)

if status == cp_model.OPTIMAL:
    print("Optimal Schedule Generated.\n")
    roleNames = {server: "Server", runner: "Runner", host: "Host"}
    for shift in houseShifts:
        shiftId = shift["id"]
        role = roleNames[shift["role"]]
        day = shift["day"]
        start = shift["start"] / 60.0
        
        filled = False
        for e in allEmployees:
            if solver.value(shifts[(e, shiftId)]) == 1:
                print(f"Day {day} | Shift ID {shiftId} ({role}, Start: {start:.1f}): Assigned to Employee {e}")
                filled = True
                break
        
        if not filled:
            print(f"Day {day} | Shift ID {shiftId} ({role}, Start: {start:.1f}): UNFILLED (Staff Shortage)")
else:
    print("No optimal schedule found.")





