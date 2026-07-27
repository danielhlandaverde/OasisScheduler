TRUNCATE TABLE employees RESTART IDENTITY CASCADE;
TRUNCATE TABLE employee_roles RESTART IDENTITY CASCADE;
TRUNCATE TABLE shift_requests RESTART IDENTITY CASCADE;
TRUNCATE TABLE house_shifts RESTART IDENTITY CASCADE;
TRUNCATE TABLE finalized_schedule RESTART IDENTITY CASCADE;
TRUNCATE TABLE historical_workloads RESTART IDENTITY CASCADE;

INSERT INTO employees (id, name, target_minutes_per_week, seniority_score, historical_minutes) VALUES
(0, 'Employee 0', 20*60, 5, 0),
(1, 'Employee 1', 10*60, 3, 0),
(2, 'Employee 2', 20*60, 3, 0),
(3, 'Employee 3', 20*60, 3, 0),
(4, 'Employee 4', 30*60, 5, 0),
(5, 'Employee 5', 10*60, 2, 0),
(6, 'Employee 6', 10*60, 2, 0),
(7, 'Employee 7', 20*60, 2, 0),
(8, 'Employee 8', 30*60, 4, 0),
(9, 'Employee 9', 20*60, 3, 0);

INSERT INTO employee_roles (employee_id, role_id) VALUES
(0, 0), (0, 1),
(1, 0),
(2, 0),
(3, 1), (3, 2),
(4, 1),
(5, 1),
(6, 0), (6, 2),
(7, 2),
(8, 2),
(9, 0), (9, 1),  (9, 2);

INSERT INTO shift_requests (employee_id, day_of_week, request_type) VALUES
(0, 0, 1), (1, 0, 1), (2, 0, 1), (3, 0, 1), (4, 0, 1), -- Monday
(5, 0, 1), (6, 0, 1), (7, 0, 1), (8, 0, 1), (9, 0, 1),
(0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0), (4, 1, 0), --tuesday
(5, 1, 0), (6, 1, 0), (7, 1, 0), (8, 1, 0), (9, 1, 0),
(0, 2, 0), (1, 2, 0), (2, 2, 0), (3, 2, 0), (4, 2, 0), --Wednesday
(5, 2, 0), (6, 2, 0), (7, 2, 0), (8, 2, 0), (9, 2, 0),
(0, 3, 0), (1, 3, 0), (2, 3, 0), (3, 3, 0), (4, 3, 0), --Thursday
(5, 3, 0), (6, 3, 0), (7, 3, 0), (8, 3, 0), (9, 3, 0),
(0, 4, 0), (1, 4, 0), (2, 4, 0), (3, 4, 0), (4, 4, 0), -- Friday
(5, 4, 0), (6, 4, 0), (7, 4, 0), (8, 4, 0), (9, 4, 0),
(0, 5, 0), (1, 5, 0), (2, 5, 0), (3, 5, 0), (4, 5, 0), --Saturday
(5, 5, 0), (6, 5, 0), (7, 5, 0), (8, 5, 0), (9, 5, 0),
(0, 6, 0), (1, 6, 0), (2, 6, 0), (3, 6, 0), (4, 6, 0), --Sunday
(5, 6, 0), (6, 6, 0), (7, 6, 0), (8, 6, 0), (9, 6, 0);

INSERT INTO house_shifts (day_of_week, role_id, start_minutes, end_minutes, is_weekend_rate) VALUES 
(0, 0, 660, 1020, FALSE), -- Monday Server 11:00 - 5:00 
(0, 0, 660, 1020, FALSE), -- Monday Server 11:00 - 5:00
(0, 1, 660, 1020, FALSE), -- Monday Runner 11:00 - 5:00
(0, 1, 690, 1020, FALSE), -- Monday Runner 11:30 - 5:00
(0, 2, 720, 1020, FALSE); -- Monday Host   12:00 - 5:00

INSERT INTO historical_workloads (employee_id, week_offset, minutes_worked) VALUES
(0, 1, 18*60), (0, 2, 14*60), (0, 3, 14*60), (0, 4, 23*60),
(1, 1, 8*60),  (1, 2, 6*60),  (1, 3, 8*60),  (1, 4, 11*60),
(2, 1, 18*60), (2, 2, 16*60), (2, 3, 10*60), (2, 4, 20*60),
(3, 1, 12*60), (3, 2, 12*60), (3, 3, 14*60), (3, 4, 22*60),
(4, 1, 27*60), (4, 2, 26*60), (4, 3, 22*60), (4, 4, 23*60),
(5, 1, 7*60),  (5, 2, 5*60),  (5, 3, 14*60), (5, 4, 7*60),
(6, 1, 18*60), (6, 2, 15*60), (6, 3, 18*60), (6, 4, 11*60),
(7, 1, 18*60), (7, 2, 18*60), (7, 3, 10*60), (7, 4, 16*60),
(8, 1, 19*60), (8, 2, 12*60), (8, 3, 20*60), (8, 4, 14*60),
(9, 1, 29*60), (9, 2, 28*60), (9, 3, 22*60), (9, 4, 25*60);

UPDATE employees e
SET historical_minutes = (
    SELECT COALESCE(SUM(minutes_worked), 0)
    FROM historical_workloads hw
    WHERE hw.employee_id = e.id
);


-- (real headcounts)
-- WEEKENDS        WEEKDAYS
-- 25 AM server    8 AM server
-- 15 AM runner    3 AM runner
-- 6 AM host       4 AM host
-- 30 PM SERVER    15 PM server
-- 16 PM runner    8 PM runner
-- 12 PM host      8 PM host

