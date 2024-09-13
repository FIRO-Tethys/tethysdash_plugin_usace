from datetime import datetime

def get_water_years(initial):
    current_date = datetime.now()
    if current_date.month > 9:
        current_water_year = current_date.year + 1
    else:
        current_water_year = current_date.year

    return [year for year in range(initial, current_water_year+1)]