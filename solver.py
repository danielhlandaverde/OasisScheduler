from ortools.sat.python import cp_model
from typing import Union
import random

numEmployees = 10
numShifts = 2
numDays = 7

allEmployees = range(numEmployees)
allShifts = range(numShifts)
allDays = range(numDays)

maxShiftsPerEmployee = 99
maxEmployeesPerShift = 5

# Row = Employee;   Column = Day;   Element = Shift (AM/PM)
# Temporarily hard-coded
shiftRequests = [
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    [[1, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
]

# Each element represents the last 4 weeks of data for that employee 
historicalShiftsRecieved = [0, 20, 22, 21, 28, 10, 6, 13, 0, 12]

# Define employees by their availability
adult_runners = [0, 1, 2, 3, 4]  # Target: ~5.5 shifts/week
teen_runners  = [5, 6, 7, 8, 9]  # Target: ~2.5 shifts/week

seniorityScores = [5, 4, 3, 3, 2,  4, 3, 2, 1, 1]

objectiveTerms = []

'''
Group employees by availability tiers. calculate fairness relative to tiers.
Adults/high availability: 5-6 shifts weekly. Teens/low availability: 1-3 shifts weekly.
Gentle seniority score as tie breaker.
'''
model = cp_model.CpModel()

# shifts[(e, d, s)]: employee 'e' works shift 's' on day 'd'
shifts = {}
for e in allEmployees:
    for d in allDays:
        for s in allShifts:
            shifts[(e, d, s)] = model.new_bool_var(f"shift_n{e}_d{d}_s{s}")

# Employees will only be scheduled when they request that shift
for e in allEmployees:
    for d in allDays:
        for s in allShifts:
            if shiftRequests[e][d][s] == 0:
                model.add(shifts[(e, d, s)] == 0)

# Employees cannot work more than 'maxShiftsPerWeek' shifts
# aka max shifts per employee 
for e in allEmployees:
    numShiftsWorked = []
    for d in allDays:
        for s in allShifts:
            numShiftsWorked.append(shifts[(e, d, s)])
    model.add(cp_model.LinearExpr.sum(numShiftsWorked) <= maxShiftsPerEmployee)

# A shift cannot contain more than 'maxEmployeesPerShift' employees
# aka max employees per shift
for d in allDays:
    for s in allShifts:
        numEmployeesPerShift = []
        for e in allEmployees:
            numEmployeesPerShift.append(shifts[(e, d, s)])
        model.add(cp_model.LinearExpr.sum(numEmployeesPerShift) <= maxEmployeesPerShift)

# This handles workforce fairness, employee seniority, and random tie-breaking
# It separates preference fulfillment (1000 pts) from priority scores to 
# ensure the solver can rank employees cleanly
for e in allEmployees:
    weeklyAverageShifts = historicalShiftsRecieved[e] / 4.0
    if e in adult_runners:
        tierTarget = 5.5
    else:
        tierTarget = 2.5
    fairnessGap = tierTarget - weeklyAverageShifts
    fairnessWeight = int(fairnessGap * 20)
    seniorityBonus = seniorityScores[e] * 5
    for d in allDays:
        for s in allShifts:
            baseReward = shiftRequests[e][d][s] * 1000 * shifts[(e, d, s)]
            noise = random.randint(0, 5) # may increase to 50 so teens can beat adults
            priorityPoints = (fairnessWeight + seniorityBonus + noise) * shifts[(e, d, s)]
            objectiveTerms.append(baseReward + priorityPoints)

model.maximize(sum(objectiveTerms))

solver = cp_model.CpSolver()
status = solver.solve(model)


if status == cp_model.OPTIMAL:
    print("Solution:")
    for d in allDays:
        print("Day", d)
        for e in allEmployees:
            for s in allShifts:
                if solver.value(shifts[(e, d, s)]) == 1:
                    if shiftRequests[e][d][s] == 1:
                        print("Employee", e, "works shift", s, "(requested).")
                    else:
                        print("Employee", e, "works shift", s, "(not requested).")
        print()
    print(
        f"Number of shift requests met = {solver.objective_value}",
        #f"(out of {numEmployees * min_shifts_per_nurse})",
    )
else:
    print("No optimal solution found !")




