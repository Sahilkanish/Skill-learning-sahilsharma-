total_bottles = int(input("Enter total water bottles: "))
bottles_per_day = int(input("Enter bottles you drink per day: "))

day = 1
while total_bottles > 0:
    drink = min(bottles_per_day, total_bottles)
    print(f"day {day} : drank {drink} bottle{'s' if drink > 1 else ''}. {total_bottles - drink} left.")
    total_bottles -= drink
    day += 1

print("No more bottles left")
