
# Step 1: Find intersection point A of l1 and l2
# l1: 2x - y - 1 = 0  => y = 2x - 1
# l2: 3x - y - 2 = 0  => y = 3x - 2
# Set y values equal: 2x - 1 = 3x - 2
# x = 1
# Substitute x back into y = 2x - 1: y = 2(1) - 1 = 1
A = (1, 1)

# Step 2: Point B
B = (-2, 2)

# Step 3: Calculate midpoint M of AB
Mx = (A[0] + B[0]) / 2
My = (A[1] + B[1]) / 2
M = (Mx, My)

# Step 4: Calculate slope of AB
slope_AB = (B[1] - A[1]) / (B[0] - A[0])

# Step 5: Calculate slope of perpendicular bisector
slope_perp = -1 / slope_AB

# Step 6: Formulate the equation of the perpendicular bisector
# Using point-slope form: y - My = slope_perp * (x - Mx)
# y = slope_perp * x - slope_perp * Mx + My
c = My - slope_perp * Mx
equation = f"y = {slope_perp}x + {c}"

print(equation)
