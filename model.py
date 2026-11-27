
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Sample training dataset
data = {
    "attendance": [
        95, 90, 85, 80, 75, 70, 65, 60, 55, 50,
        98, 92, 88, 82, 78, 72, 68, 62, 58, 45
    ],
    "marks": [
        92, 88, 85, 80, 75, 70, 65, 60, 50, 40,
        96, 90, 86, 82, 76, 72, 66, 55, 48, 35
    ],
    "performance": [
        "Excellent", "Excellent", "Excellent", "Good",
        "Good", "Good", "Average", "Average", "At Risk",
        "At Risk", "Excellent", "Excellent", "Good",
        "Good", "Good", "Average", "Average", "At Risk",
        "At Risk", "At Risk"
    ]
}

df = pd.DataFrame(data)

# Features and target
X = df[["attendance", "marks"]]
y = df["performance"]

# Train Machine Learning Model
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X, y)


# Prediction Function
def predict_performance(attendance, marks):

    prediction = model.predict(
        pd.DataFrame(
            [[attendance, marks]],
            columns=["attendance", "marks"]
        )
    )

    return prediction[0]
