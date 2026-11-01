
import pickle

model_path = "models/severity_model.pkl"

try:
    with open(model_path, "rb") as file:
        model = pickle.load(file)

    print("BugFlow Severity Prediction")
    print("---------------------------")

    while True:
        description = input(
            "\nEnter bug description (or type 'exit' to stop): "
        )

        if description.lower() == "exit":
            print("Testing finished.")
            break

        if not description.strip():
            print("Please enter a bug description.")
            continue

        severity = model.predict([description])[0]
        probabilities = model.predict_proba([description])[0]
        confidence = max(probabilities) * 100

        print("Predicted severity:", severity)
        print("Model confidence:", round(confidence, 2), "%")

except FileNotFoundError:
    print("Model not found. Run python train_model.py first.")
