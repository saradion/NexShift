from ortools.sat.python import cp_model

model = cp_model.CpModel()                      # 1. an empty "problem"
nurses, days = range(3), range(3)

# 2. VARIABLES: x[n, d] = 1 means "nurse n works on day d", 0 means not
x = {(n, d): model.NewBoolVar(f"x_{n}_{d}") for n in nurses for d in days}

# 3. HARD CONSTRAINTS: rules that must never be broken
for d in days:
    model.Add(sum(x[n, d] for n in nurses) == 1)   # exactly one nurse per day
for n in nurses:
    model.Add(sum(x[n, d] for d in days) <= 1)     # nobody works more than one day

# 4. OBJECTIVE: nurse 0 prefers not to work day 0, so make that costly
model.Minimize(10 * x[0, 0])

solver = cp_model.CpSolver()                    # 5. the engine that searches
status = solver.Solve(model)
print(solver.StatusName(status))                # OPTIMAL / FEASIBLE / INFEASIBLE

for d in days:
    for n in nurses:
        if solver.Value(x[n, d]):
            print(f"day {d}: nurse {n}")