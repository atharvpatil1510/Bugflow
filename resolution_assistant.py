
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

print("Loading historical bug reports...")

df = pd.read_csv("data/bug_reports_clean.csv")

# Keep the descriptions and their historical severity labels
df = df.dropna(subset=["Short Description", "Severity Label"])
df = df.reset_index(drop=True)

# Convert bug descriptions into numerical text features
vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words="english",
    max_features=20000
)

tfidf_matrix = vectorizer.fit_transform(df["Short Description"])

print("Resolution assistant is ready!")


def find_similar_bugs(description, top_n=5):
    query_vector = vectorizer.transform([description])

    similarities = cosine_similarity(
        query_vector,
        tfidf_matrix
    ).flatten()

    # Find the most similar historical descriptions
    top_indices = similarities.argsort()[::-1]

    results = []

    for index in top_indices:
        if similarities[index] <= 0:
            break

        results.append({
            "description": df.iloc[index]["Short Description"],
            "severity": df.iloc[index]["Severity Label"],
            "similarity": round(float(similarities[index]) * 100, 2)
        })

        if len(results) == top_n:
            break

    return results


if __name__ == "__main__":
    while True:
        description = input(
            "\nEnter a bug description (or type 'exit'): "
        ).strip()

        if description.lower() == "exit":
            print("Goodbye!")
            break

        if not description:
            print("Please enter a description.")
            continue

        matches = find_similar_bugs(description)

        if not matches:
            print("No sufficiently similar historical reports found.")
            continue

        print("\nSimilar historical bug reports:")

        for number, bug in enumerate(matches, start=1):
            print(f"\n{number}. {bug['description']}")
            print(f"   Severity: {bug['severity']}")
            print(f"   Similarity: {bug['similarity']}%")
