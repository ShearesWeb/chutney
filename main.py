import numpy as np
import pandas as pd

# Variable to store weekly charge
WEEKLY_CHARGE = 125.00

# This specifies the week ranges
# To apply the charges and subsidies, we define what each
# week is and the corresponding dates
# Format it as dd/mm/yyyy
weeks = [
    ['10/12/2023','17/12/2023'],
    ['18/12/2023','24/12/2023'],
    ['25/12/2023','31/12/2023'],
    ['01/01/2024','07/01/2024'],
    ['08/01/2024','14/01/2024'],
]

weeks_original_dates = []
for w in weeks:
    weeks_original_dates.append(w.copy())

class Category:
    def __init__(self, name, rates):
        '''
        Expects the name,
        rates of the hours 
        '''
        self.name = name
        self.rates = rates

    def get_subsidy(self, hours):
        '''
        Returns subsidy as a percentage
        '''
        for i in range(len(self.rates) - 1, -1, -1):
            if hours >= self.rates[i][0]:
                return self.rates[i][1]

# Categories store the category name
# and the susbsidy rates in a 2d array
# e.g [12, 0.2], [18, 0.3] means if the hours are >= 12 hours, the subsidy is 20%
# if the hours are >= 18 hours, the subsidy is 30%

categories = {
    'A': Category('A', [[0,0], [12, 0.2], [18, 0.3], [24, 0.4]]),
    'B': Category('B', [[0,0], [8, 0.15], [13, 0.25], [18, 0.35]]),
    'C': Category('C', [[0,0], [10, 0.15], [20, 0.30], [30, 0.45]]),
    'D1': Category('D1', [[0,0], [30, 0.40], [40, 0.60], [45, 0.70]]),
    'D2': Category('D2', [[0,0], [12, 0.20], [21, 0.35], [30, 0.50]]),
}

# Converts the weeks specified as string
# to pandas data range for us to do the checking
# of when the check-in check-out daetes matches etc.
for i in range(len(weeks)):
    for j in range(len(weeks[i])):
        weeks[i][j] = pd.to_datetime(weeks[i][j], dayfirst=True)
    weeks[i] = pd.date_range(start=weeks[i][0], end=weeks[i][1], freq='D')

df = pd.read_csv("check-in-dates.csv", parse_dates=['Check In Date', 'Check Out Date'], dayfirst=True)
rows = df.iterrows()

people = {}
'''
This creates a dictionary where the matriculation number is the key
and the value is a list of the number of days they stayed in each week
based on the provided Check In and Check Out dates
'''
for i, row in rows:
    if row['Matriculation'] not in people:
        people[row['Matriculation']] = [0] * len(weeks)
    for i in range(len(weeks)):
        week = weeks[i]
        for date in week:
            if row['Check In Date'] <= date <= row['Check Out Date']:
                people[row['Matriculation']][i] += 1
        # Apply pro-rating
        people[row['Matriculation']][i] = people[row['Matriculation']][i] / 7 * WEEKLY_CHARGE

hours_csv = pd.read_csv("hours.csv")

# Converts values in the column from e.g "Category B: Cultural Groups" -> "B"
hours_csv["CCA Type"] = hours_csv["CCA Type"].str.split(" ").str[1].str[:-1]

# Convert week from "Week 1: 10/12/23-17/12/23" -> "1": str -> 1: int
hours_csv["Week"] = hours_csv["Week"].str.split(" ").str[1].str[:-1].astype(int)

# This sums up the hours for each student for each week and category
grouped_hours = hours_csv.groupby(["Matriculation", "Week", "CCA Type"]).sum('Hours').iterrows()

people_subsidies = {}
'''
`people_subsidies` is a dictionary where the structure is a clone
of `people` but instead of the number of days stayed, it's the
total subsidy rate for each week
'''
for i, row in grouped_hours:
    matriculation, week_no, category = row.name
    matriculation = matriculation.strip()
    # There's this weird text encoding issue where there's a soft hyphen in the category name
    category = category.strip().replace("\xad", "")
    week_no = week_no - 1 # Have to offset by 1 for zero-indexing
    hours = row['Hours']
    if matriculation not in people:
        print(f"Error! Matriculation {matriculation} not found!")
        continue

    if matriculation not in people_subsidies:
        people_subsidies[matriculation] = [0] * len(weeks)

    if category not in categories:
        print(matriculation, week_no, category)
        print(f"Error! Category{category}not found!")
        break

    people_subsidies[matriculation][week_no] += categories[category].get_subsidy(hours)
    people_subsidies[matriculation][week_no] = min(0.75, categories[category].get_subsidy(hours))

weekly_charges_pre_subsidy = []
# Function that calculates total charges before subsidies
for matriculation in people:
    weeks = people[matriculation]
    for i in range(len(weeks)):
        weekly_charges_pre_subsidy.append([matriculation, f"Week {i+1}: {weeks_original_dates[i][0]} - {weeks_original_dates[i][1]}", weeks[i]])

# Saves the charges before subsidies to a csv file
pd.DataFrame(weekly_charges_pre_subsidy, columns=["Matriculation", "Week", "Billable Amount (Before Subsidy)"]).to_csv("weekly_charges.csv", index=False)


result = []
'''
Takes the list of weekly charges pre-subsidy and applies the subsidies
into the `result` array
'''
for matriculation in people:
    weekly_charges_pre_subsidy = people[matriculation]
    subsidies = people_subsidies.get(matriculation)
    for i in range(len(weekly_charges_pre_subsidy)):
        if subsidies is not None:
            weekly_charges_pre_subsidy[i] = weekly_charges_pre_subsidy[i] * (1 - subsidies[i])
        result.append([matriculation, f"Week {i+1}: {weeks_original_dates[i][0]} - {weeks_original_dates[i][1]}", weeks[i]])

# Intermediate step where we check if the weekly charge is 0 we don't include
# (For cases where students didn't stay in the hostel for that week)
result = list(filter(lambda row: row[2] != 0, result))
pd.DataFrame(result, columns=["Matriculation", "Week", "Billable Amount (After Subsidies)"]).to_csv("result.csv", index=False)
# Filter based on a specific Marticulation