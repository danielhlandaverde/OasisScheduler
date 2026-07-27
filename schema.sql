DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS employee_roles CASCADE;
DROP TABLE IF EXISTS shift_requests CASCADE;
DROP TABLE IF EXISTS house_shifts CASCADE;
DROP TABLE IF EXISTS finalized_schedule CASCADE;
DROP TABLE IF EXISTS historical_workloads CASCADE;

CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
	seniority_score INT DEFAULT 1,
    target_minutes_per_week INT DEFAULT 0,
    historical_minutes INT DEFAULT 0
);

CREATE TABLE employee_roles (
	employee_id INT,
	role_id INT, -- 0: Server, 1: Runner, 2: Host
	PRIMARY KEY(employee_id, role_id),
	FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE shift_requests (
	id serial PRIMARY KEY,
	employee_id INT NOT NULL,
	day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0: Monday, 6: Sunday
	request_type INT NOT NULL CHECK (request_type BETWEEN 0 AND 3), -- 0: NONE, 1: AM, 2: PM, 3: DBL, 4: AM/PM
	FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE TABLE house_shifts (
	id serial PRIMARY KEY,
	day_of_week INT,
	role_id INT,
	start_minutes INT,
	end_minutes INT,
	is_weekend_rate BOOLEAN DEFAULT FALSE
);

CREATE TABLE finalized_schedule (
	shift_id INT PRIMARY KEY,
	employee_id INT,
	is_published BOOLEAN DEFAULT FALSE,
	FOREIGN KEY (shift_id) REFERENCES house_shifts(id) ON DELETE CASCADE,
	FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
);

-- individually tracks each week of data for each employee,
-- to be fed into 'historical_minutes' row in 'employees' table
-- on a rolling window of 4 weeks
CREATE TABLE historical_workloads (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
    week_offset INT CHECK (week_offset IN (1, 2, 3, 4)), -- 1: last week, 4: 4 weeks ago
    minutes_worked INT DEFAULT 0
);